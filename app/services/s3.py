import os
import logging
from botocore.exceptions import NoCredentialsError
from fastapi import HTTPException, status
from app.core.config import settings
import boto3
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(_name_)

# Initialize the S3 client
s3_client = boto3.client(
    's3',
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)


def download_file_from_s3(s3_key: str, bucket_name: str):
    try:
        # Use Path to construct a cross-platform file path
        # Default to current working directory if TEMP is unavailable
        temp_dir = Path(os.getenv('TEMP', Path.cwd()))
        local_file_path = temp_dir / os.path.basename(s3_key)

        logger.info(f"Downloading file from S3: s3://{bucket_name}/{s3_key}")
        s3_client.download_file(bucket_name, s3_key, str(local_file_path))
        logger.info(
            f"File downloaded successfully. Local path: {local_file_path}")

        return str(local_file_path)
    except NoCredentialsError:
        logger.error("S3 credentials are missing or incorrect.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="S3 credentials are missing or incorrect."
        )
    except Exception as e:
        logger.error(f"Failed to download file from S3: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file from S3: {str(e)}"
        )


def upload_file_to_s3(file_path: str, s3_key: str, bucket_name: str):
    try:
        logger.info(f"Uploading file to S3: s3://{bucket_name}/{s3_key}")
        s3_client.upload_file(file_path, bucket_name, s3_key)
        logger.info(f"File uploaded successfully. S3 key: {s3_key}")
        return f"s3://{bucket_name}/{s3_key}"
    except NoCredentialsError:
        logger.error("S3 credentials are missing or incorrect.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="S3 credentials are missing or incorrect."
        )
    except Exception as e:
        logger.error(f"Failed to upload file to S3: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )
