import os
import logging
import nibabel as nib
import numpy as np
from PIL import Image
from app.services.s3 import upload_file_to_s3
from fastapi import HTTPException, status

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

        metadata = {}
        for view, slices in views.items():
            s3_folder = f"{os.path.dirname(s3_key)}/{view}/"
            logger.info(f"Saving and uploading {view} slices to: {s3_folder}")
            slice_count = save_and_upload_slices(slices, s3_folder, view, bucket_name)
            if slice_count > 0:
                metadata[view] = {
                    "num_slices": slice_count,
                    "folder_key": s3_folder
                }

        return metadata

    except Exception as e:
        logger.error(f"Failed to process .nii file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process .nii file: {str(e)}"
        )

def save_and_upload_slices(slices, s3_folder, prefix, bucket_name):
    slice_count = 0
    for i, slice in enumerate(slices):
        try:
            # Normalize slice data to range 0-255 for image saving
            slice_normalized = (slice - np.min(slice)) / (np.max(slice) - np.min(slice)) * 255
            slice_normalized = slice_normalized.astype(np.uint8)

            # Convert to image and save locally
            img = Image.fromarray(slice_normalized)
            local_file_path = f"/tmp/{prefix}_slice_{i}.jpg"
            img.save(local_file_path)
            logger.info(f"Saved slice {i} locally at: {local_file_path}")

            # Upload to S3
            upload_file_to_s3(local_file_path, f"{s3_folder}{prefix}_slice_{i}.jpg", bucket_name)
            logger.info(f"Uploaded slice {i} to S3 path: {s3_folder}{prefix}_slice_{i}.jpg")
            slice_count += 1

            # Remove the local file after upload to save space
            os.remove(local_file_path)
        except Exception as e:
            logger.error(f"Error processing slice {i}: {str(e)}")

    return slice_count
