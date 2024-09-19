import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.services.file_processing import process_nii_file
from app.services.s3 import download_file_from_s3
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class FileProcessingRequest(BaseModel):
    s3_key: str = Field(..., description="S3 key where the file is located.")
    bucket_name: str = Field(..., description="S3 bucket name containing the file.")

@router.post("/file-processing", response_class=JSONResponse)
async def file_processing(request: FileProcessingRequest):
    logger.info("Received request to process file.")
    
    try:
        logger.info("Starting file download from S3.")
        file_path = download_file_from_s3(request.s3_key, request.bucket_name)
        logger.info(f"File downloaded successfully. File path: {file_path}")

        logger.info("Starting NIfTI file processing.")
        metadata = process_nii_file(file_path, request.s3_key, request.bucket_name)
        logger.info("NIfTI file processing completed successfully.")

        return {
            "message": "File processed successfully.",
            "metadata": metadata
        }
    except HTTPException as e:
        logger.error(f"HTTPException occurred: {str(e.detail)}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"File processing failed: {str(e)}"
        )
