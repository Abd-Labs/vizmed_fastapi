from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
import traceback
import requests
from app.services.file_processing import process_nii_file
from app.services.common_services import get_local_file_path
from app.services.s3 import download_file_from_s3
from app.core.config import settings
import platform
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Request model for file processing
class FileProcessingRequest(BaseModel):
    s3_key: str = Field(..., description="S3 key where the file is located.")
    bucket_name: str = Field(..., description="S3 bucket name containing the file.")
    callback_url: str = Field(..., description="Node.js server callback URL to send metadata.")
    user_id: str = Field(..., description="ID of the user the MRI belongs to.")
    patient_id: str = Field(..., description="ID of the patient the MRI belongs to.")
    mriFileId: str = Field(..., description="ID of MRI file object saved in MongoDB")

@router.post("/file-processing", status_code=status.HTTP_202_ACCEPTED)
async def file_processing(request: FileProcessingRequest, background_tasks: BackgroundTasks):
    try:

        adjusted_callback_url = request.callback_url

        if settings.IS_DOCKER and "localhost" in request.callback_url:
                # Adjust callback URL based on OS
                if platform.system() in ["Darwin", "Windows"]:
                    adjusted_callback_url = request.callback_url.replace("localhost", "host.docker.internal")
                elif platform.system() == "Linux":
                    adjusted_callback_url = request.callback_url.replace("localhost", "172.17.0.1")

        # Schedule file processing in the background
        background_tasks.add_task(
            process_file, 
            request.s3_key, 
            request.bucket_name, 
            adjusted_callback_url, 
            request.user_id,
            request.patient_id,
            request.mriFileId
        )

        # Immediately respond to Node.js server
        return {"message": "File processing started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting file processing: {str(e)}")

# Function to process the file and send metadata back to Node.js
def process_file(s3_key: str, bucket_name: str, callback_url: str, user_id: str, patient_id: str, mriFileId: str):
    try:
        
        local_file_path = get_local_file_path(s3_key)

        # Download and process the file
        file_path = download_file_from_s3(s3_key, bucket_name,local_file_path)
        result = process_nii_file(file_path, s3_key, bucket_name)  # Contains both metadata and zip_file_key

        # Construct the payload with the required fields
        payload = {
            "zip_file_key": result["zip_file_key"],
            "metadata": result["metadata"],
            "user_id": user_id,
            "patient_id": patient_id,
            "mriFileId": mriFileId
        }

        # Send the payload to the Node.js callback URL
        response = requests.post(callback_url, json=payload)

        if response.status_code != 200:
            logger.error(f"Failed to send metadata to Node.js (status: {response.status_code}): {response.text}")
        else:
            logger.info(f"Successfully sent metadata to Node.js: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"RequestException while sending metadata to Node.js: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")
    except Exception as e:
        logger.error(f"General error occurred while processing file: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")

