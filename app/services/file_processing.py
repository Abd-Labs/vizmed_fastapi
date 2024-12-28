import os
import numpy as np
import nibabel as nib
from PIL import Image
from zipfile import ZipFile
import logging
from app.services.s3 import upload_file_to_s3
from app.services.common_services import create_temp_directory, delete_temp_directory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_nii_file(file_path: str, s3_key: str, bucket_name: str):
    logger.info("Starting processing of NIfTI file: %s", file_path)
    try:
        nii_img = nib.load(file_path)
        nii_data = nii_img.get_fdata()
        affine = nii_img.affine
        axis_dict = determine_axes(affine)
        
        # Temporary directory setup
        base_dir = create_temp_directory(s3_key)
        zip_file_path = base_dir / f"{os.path.basename(os.path.dirname(s3_key))}_mri_slices.zip"
        metadata = {}

        with ZipFile(zip_file_path, 'w') as zipf:
            for plane in ["axial", "coronal", "sagittal"]:
                view_dir = f"{os.path.dirname(s3_key)}/{plane}/"
                os.makedirs(base_dir / plane, exist_ok=True)
                
                axis = axis_dict[plane]
                slice_count = save_slices_to_zip(nii_data, axis, plane, zipf, view_dir)
                
                if slice_count > 0:
                    metadata[plane] = {"num_slices": slice_count, "folder_key": view_dir}
                    logger.info("Processed %d slices for %s view", slice_count, plane)
                else:
                    logger.warning("No slices found for %s view", plane)

        # Upload the zip file to S3
        s3_zip_key = f"{os.path.dirname(s3_key)}/mri_slices.zip"
        upload_file_to_s3(str(zip_file_path), s3_zip_key, bucket_name)
        logger.info("Uploaded zip file to S3 with key: %s", s3_zip_key)
        zip_file_path.unlink()  # Remove the local zip file

        delete_temp_directory(base_dir)  # Clean up
        logger.info("Temporary directory cleaned up: %s", base_dir)

        return {"zip_file_key": s3_zip_key, "metadata": metadata}

    except Exception as e:
        logger.error("Failed to process NIfTI file: %s", str(e), exc_info=True)
        raise e


def determine_axes(affine):
    orientation = nib.aff2axcodes(affine)
    axis_dict = {'sagittal': None, 'coronal': None, 'axial': None}
    for idx, axis in enumerate(orientation):
        if axis in ('R', 'L'):
            axis_dict['sagittal'] = idx
        elif axis in ('A', 'P'):
            axis_dict['coronal'] = idx
        elif axis in ('S', 'I'):
            axis_dict['axial'] = idx
    logger.debug("Determined axes for slicing: %s", axis_dict)
    return axis_dict

def save_slices_to_zip(data, axis, prefix, zipf, view_dir):
    slice_count = 0
    logger.info("Saving slices for %s view", prefix)
    for i in range(data.shape[axis]):
        try:
            slice_data = np.take(data, i, axis=axis)
            
            # Check if slice has uniform values to avoid divide by zero
            if np.max(slice_data) == np.min(slice_data):
                # If uniform, set the slice to a gray image
                slice_normalized = np.full(slice_data.shape, 127, dtype=np.uint8)
                logger.warning("Slice %d for %s view is uniform; using gray image.", i, prefix)
            else:
                # Normalize slice data
                slice_normalized = (slice_data - np.min(slice_data)) / (np.max(slice_data) - np.min(slice_data)) * 255
                slice_normalized = slice_normalized.astype(np.uint8)
            
            # Create an image and rotate if necessary
            img = Image.fromarray(slice_normalized).rotate(180)

            img_filename = f"{view_dir}{prefix}_slice_{i}.jpg"
            with zipf.open(img_filename, 'w') as img_file:
                img.save(img_file, format='JPEG')
            slice_count += 1
        except Exception as e:
            logger.warning("Error processing slice %d for %s view: %s", i, prefix, str(e))
            continue
    logger.info("Finished saving %d slices for %s view", slice_count, prefix)
    return slice_count
