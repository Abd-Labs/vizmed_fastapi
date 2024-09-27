import os
import logging
import nibabel as nib
import numpy as np
from PIL import Image
from zipfile import ZipFile
from app.services.s3 import upload_file_to_s3
from fastapi import HTTPException, status
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_nii_file(file_path: str, s3_key: str, bucket_name: str):
    try:
        logger.info(f"Processing NIfTI file: {file_path}")
        nii_img = nib.load(file_path)
        nii_data = nii_img.get_fdata()

        # Extract slices and organize them in Axial, Sagittal, Coronal views
        views = {
            "axial": nii_data[:, :, :],
            "sagittal": nii_data[:, :, :],
            "coronal": nii_data[:, :, :]
        }

        # Create a local directory that mirrors the S3 key (excluding the file name)
        base_dir = f"/tmp/{os.path.dirname(s3_key)}"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

        metadata = {}
        for view, slices in views.items():
            view_dir = os.path.join(base_dir, view)
            os.makedirs(view_dir, exist_ok=True)
            logger.info(f"Saving {view} slices locally at: {view_dir}")
            
            slice_count = save_slices_locally(slices, view_dir, view)
            if slice_count > 0:
                metadata[view] = {
                    "num_slices": slice_count,
                    "folder_key": f"{os.path.dirname(s3_key)}/{view}/"
                }

        # Zip the entire base directory (with subfolders for views)
        zip_file_path = f"/tmp/{os.path.basename(os.path.dirname(s3_key))}_mri_slices.zip"
        zip_slices(base_dir, zip_file_path)

        # Upload the zip file to S3
        s3_zip_key = f"{os.path.dirname(s3_key)}/mri_slices.zip"
        upload_file_to_s3(zip_file_path, s3_zip_key, bucket_name)

        # Clean up the local files
        shutil.rmtree(base_dir)  # Remove the local folder with slices
        os.remove(zip_file_path)  # Remove the zip file

        metadata["zip_file_key"] = s3_zip_key

        return metadata

    except Exception as e:
        logger.error(f"Failed to process .nii file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process .nii file: {str(e)}"
        )

def save_slices_locally(slices, save_dir, prefix):
    slice_count = 0
    for i, slice in enumerate(slices):
        try:
            # Normalize slice data to range 0-255 for image saving
            slice_normalized = (slice - np.min(slice)) / (np.max(slice) - np.min(slice)) * 255
            slice_normalized = slice_normalized.astype(np.uint8)

            # Convert to image and save locally
            img = Image.fromarray(slice_normalized)
            local_file_path = os.path.join(save_dir, f"{prefix}_slice_{i}.jpg")
            img.save(local_file_path)
            logger.info(f"Saved slice {i} locally at: {local_file_path}")
            slice_count += 1
        except Exception as e:
            logger.error(f"Error processing slice {i}: {str(e)}")

    return slice_count

def zip_slices(folder_path, zip_file_path):
    try:
        logger.info(f"Zipping folder: {folder_path}")
        with ZipFile(zip_file_path, 'w') as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)  # Relative path in zip
                    zipf.write(file_path, arcname)
        logger.info(f"Zipped folder into: {zip_file_path}")
    except Exception as e:
        logger.error(f"Error zipping folder {folder_path}: {str(e)}")
        raise e
