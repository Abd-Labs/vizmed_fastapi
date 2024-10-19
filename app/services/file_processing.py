import os
import logging
import nibabel as nib
import numpy as np
from PIL import Image
from zipfile import ZipFile
from app.services.s3 import upload_file_to_s3
from fastapi import HTTPException, status
from app.services.common_services import create_temp_directory,delete_temp_directory
import shutil
from pathlib import Path

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

        base_dir = create_temp_directory(s3_key)

        metadata = {}
        for view, slices in views.items():
            view_dir = base_dir / view
            view_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Saving {view} slices locally at: {view_dir}")

            slice_count = save_slices_locally(slices, view_dir, view)
            if slice_count > 0:
                metadata[view] = {
                    "num_slices": slice_count,
                    "folder_key": f"{os.path.dirname(s3_key)}/{view}/"
                }

        # Zip the entire base directory (with subfolders for views)
        zip_file_path = base_dir / \
            f"{os.path.basename(os.path.dirname(s3_key))}_mri_slices.zip"
        zip_slices(base_dir, zip_file_path)

        # Upload the zip file to S3
        s3_zip_key = f"{os.path.dirname(s3_key)}/mri_slices.zip"
        upload_file_to_s3(str(zip_file_path), s3_zip_key, bucket_name)

        zip_file_path.unlink()  # Remove the zip file

        # Clean up the local files
        delete_temp_directory(base_dir)  # Remove the patient-specific temp directory

        data = {
            "zip_file_key": s3_zip_key,  # Add the zip file key
            "metadata": metadata  # Add the metadata object
        }

        return data

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
            slice_normalized = (slice - np.min(slice)) / \
                (np.max(slice) - np.min(slice)) * 255
            slice_normalized = slice_normalized.astype(np.uint8)

            # Convert to image and save locally
            img = Image.fromarray(slice_normalized)
            local_file_path = save_dir / f"{prefix}slice{i}.jpg"
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
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(
                        folder_path)  # Relative path in zip
                    zipf.write(file_path, arcname)
        logger.info(f"Zipped folder into: {zip_file_path}")
    except Exception as e:
        logger.error(f"Error zipping folder {folder_path}: {str(e)}")
        raise e
