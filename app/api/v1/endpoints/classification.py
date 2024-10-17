from fastapi import APIRouter, HTTPException,BackgroundTasks
from pydantic import BaseModel
from app.services.classification_services import classify_mri_file
from app.services.common_services import get_local_file_path, delete_local_directory
router = APIRouter()

# Request model for classification


class ClassificationRequest(BaseModel):
    s3_key: str
    bucket_name: str


@router.post("/classify")
async def classify_mri(request: ClassificationRequest, background_tasks: BackgroundTasks):
    try:

        # Recreate the local file path based on s3_key
        local_file_path = get_local_file_path(request.s3_key)

        # Call the classify function with s3_key and bucket_name
        result = classify_mri_file(request.s3_key, request.bucket_name, local_file_path)

        # Schedule deletion of the file after the classification is done
        background_tasks.add_task(delete_local_directory, local_file_path)


        return {"classification": result}
    
    except FileNotFoundError as e:

        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:

        raise HTTPException(
            status_code=500, detail="An error occurred during classification")
