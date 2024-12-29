import os
import logging
import nibabel as nib
import numpy as np
from PIL import Image
from io import BytesIO
from zipfile import ZipFile
from app.services.s3 import upload_file_to_s3
from app.services.common_services import create_temp_directory, delete_temp_directory
from fastapi import HTTPException, status
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil  # To ensure the temp directory is removed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_nii_file(file_path: str, s3_key: str, bucket_name: str):
    try:
        logger.info(f"Processing NIfTI file: {file_path}")
        nii_img = nib.load(file_path)
        nii_data = nii_img.get_fdata()
        affine = nii_img.affine  # Get affine matrix

        global_min, global_max = np.min(nii_data), np.max(nii_data)
        metadata = {}

        # Determine correct axes for axial, sagittal, and coronal planes
        axis_map = determine_axes(affine)

        # Create a temporary directory for storing slices
        temp_dir = create_temp_directory(s3_key)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for view, axis in axis_map.items():
                # Extract and save slices concurrently for each view
                futures.append(executor.submit(save_slices_for_view, nii_data, view, axis, temp_dir, global_min, global_max, s3_key))
                
            for future in futures:
                view, slice_count, folder_key = future.result()
                if slice_count > 0:
                    logger.info(f"{slice_count} slices for the {view} view are extracted from the mri file")
                    metadata[view] = {"num_slices": slice_count, "folder_key": folder_key}

        zip_file_path = temp_dir / f"{os.path.basename(os.path.dirname(s3_key))}_mri_slices.zip"
        zip_slices(temp_dir, zip_file_path, exclude_extensions=[".nii"])

        # Upload the zip file to S3
        s3_zip_key = f"{os.path.dirname(s3_key)}/mri_slices.zip"
        upload_file_to_s3(str(zip_file_path), s3_zip_key, bucket_name)

        data = {
            "zip_file_key": s3_zip_key,
            "metadata": metadata
        }

        return data

    except Exception as e:
        logger.error(f"Failed to process .nii file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process .nii file: {str(e)}"
        )
    finally:
        # Cleanup the temporary directory
        delete_temp_directory(temp_dir)

def save_slices_for_view(nii_data, view, axis, base_dir, global_min, global_max, s3_key):
    view_dir = base_dir / view
    view_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving {view} slices to {view_dir}")

    slice_count = 0
    for i in range(nii_data.shape[axis]):
        slice_data = np.take(nii_data, i, axis=axis)
        slice_normalized = ((slice_data - global_min) / (global_max - global_min) * 255).astype(np.uint8)
        
        # Convert to image in memory
        img = Image.fromarray(slice_normalized)
        img_buffer = BytesIO()
        img.save(img_buffer, format="JPEG")
        img_buffer.seek(0)

        # Save the in-memory image buffer to the zip file path
        img_path = view_dir / f"{view}_slice_{i}.jpg"
        with open(img_path, "wb") as f:
            f.write(img_buffer.getvalue())

        img_buffer.close()
        slice_count += 1

    logger.info(f"Successfully saved slices of {view} view in local directory {view_dir}")

    return view, slice_count, f"{os.path.dirname(s3_key)}/{view}/"

# Function to determine correct axes for axial, sagittal, and coronal planes based on affine matrix
def determine_axes(affine):
    logger.info(f"Affine matrix: {affine}")
    orientation = nib.aff2axcodes(affine)
    logger.info(f"Orientation (aff2axcodes): {nib.aff2axcodes(affine)}")
    axis_dict = {'sagittal': None, 'coronal': None, 'axial': None}
    
    for idx, axis in enumerate(orientation):
        if axis in ('R', 'L'):
            axis_dict['sagittal'] = idx  # Sagittal plane
        elif axis in ('A', 'P'):
            axis_dict['coronal'] = idx  # Coronal plane
        elif axis in ('S', 'I'):
            axis_dict['axial'] = idx  # Axial plane
    
    return axis_dict


def zip_slices(folder_path, zip_file_path, exclude_extensions=None):
    try:
        logger.info(f"Zipping folder: {folder_path}")
        with ZipFile(zip_file_path, 'w') as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if exclude_extensions and Path(file).suffix in exclude_extensions:
                        continue
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(folder_path)
                    zipf.write(file_path, arcname)
        logger.info(f"Zipped folder into: {zip_file_path}")
    except Exception as e:
        logger.error(f"Error zipping folder {folder_path}: {str(e)}")
        raise e
