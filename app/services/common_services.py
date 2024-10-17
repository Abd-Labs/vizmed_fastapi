import os
from pathlib import Path
import logging
import shutil


logger = logging.getLogger(__name__)


def get_local_file_path(s3_key: str) -> Path:

    # Get the path to the root of the project
    project_root = Path(__file__).resolve().parent.parent.parent

    # Use the TEMP environment variable or default to project root
    temp_dir = Path(os.getenv('TEMP', project_root))

    # Remove the file name and keep only the directory structure from the S3 key
    local_dir_path = temp_dir / 'tmp' / s3_key  # This gives the directory path

    return local_dir_path
    
# Helper function to delete an entire directory
def delete_local_directory(directory_path: str):
    try:
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
            logger.info(f"Successfully deleted directory and its contents: {directory_path}")
        else:
            logger.warning(f"Directory not found for deletion: {directory_path}")
    except Exception as e:
        logger.error(f"Error deleting directory {directory_path}: {str(e)}")
