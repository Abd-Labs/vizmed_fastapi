from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from app.services.mri_colorization_service import colorize_mri_image
from app.core.config import settings
import numpy as np
import cv2
import tempfile
import logging
import os

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

def validate_file_extension(filename: str) -> bool:
    # Check if the file has one of the allowed extensions
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@router.post("/colorize-mri-slice/")
async def colorize_mri_slice(image_file: UploadFile = File(...)):
    # Validate file extension
    if not validate_file_extension(image_file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .jpg, .jpeg, and .png files are allowed.")

    try:
        # Load MRI slice image from the request
        logger.info("Receiving MRI slice image for colorization.")
        image_data = np.frombuffer(await image_file.read(), np.uint8)
        mri_slice_image = cv2.imdecode(image_data, cv2.IMREAD_GRAYSCALE)

        if mri_slice_image is None:
            raise HTTPException(status_code=400, detail="Invalid MRI slice image.")

        # Load the color spectrum from static file path
        logger.info(f"Loading color spectrum file at path: {settings.COLOR_SPECTRUM_FILE_PATH}")
        color_spectrum_path = settings.COLOR_SPECTRUM_FILE_PATH
        if not os.path.exists(color_spectrum_path):
            raise HTTPException(status_code=500, detail="Color spectrum file not found.")
        
        color_spectrum = cv2.imread(color_spectrum_path, cv2.IMREAD_COLOR)
        if color_spectrum is None:
            raise HTTPException(status_code=500, detail="Error loading color spectrum image.")

        # Colorize the MRI slice image
        colorized_image = colorize_mri_image(mri_slice_image, color_spectrum)

        # Save colorized image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            colorized_image_path = tmp_file.name
            cv2.imwrite(colorized_image_path, colorized_image)
            logger.info(f"Colorized MRI slice image saved temporarily at {colorized_image_path}")
        
        return FileResponse(colorized_image_path, media_type="image/jpeg", filename="colorized_mri_slice.jpg")
    
    except Exception as e:
        logger.error(f"Error processing MRI slice colorization: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while processing the MRI slice image.")
