from pathlib import Path
import logging
import shutil
from app.core.config import settings

logger = logging.getLogger(__name__)



def get_local_file_path(s3_key: str) -> Path:
    # Use the ROOT_DIR variable from settings
    root_dir = Path(settings.ROOT_DIR)

    # Split the S3 key into parts
    s3_parts = Path(s3_key).parts

    # Assuming the patient ID is the last part before the file name
    resource_id = s3_parts[-2]
    file_name = s3_parts[-1]

    # Create the local directory path as root_dir/mri/patient_id
    local_dir_path = root_dir / 'mri' / resource_id / file_name

    return local_dir_path

    
def delete_local_file(file_path: Path):
    try:
        # Check if the file exists
        if file_path.exists():
            # Delete the file
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
        else:
            logger.warning(f"File does not exist: {file_path}")

        # Get the parent directory, which is the patient-specific directory
        patient_dir = file_path.parent

        # Check if the patient-specific directory is empty
        if not any(patient_dir.iterdir()):  # If the directory is empty
            shutil.rmtree(patient_dir)  # Remove the patient directory
            logger.info(f"Deleted patient directory: {patient_dir}")
        else:
            logger.info(f"Patient directory is not empty: {patient_dir}")

    except Exception as e:
        logger.error(f"Error during deletion: {str(e)}")
        raise e
    

def create_temp_directory(s3_key: str) -> Path:

    # Use the ROOT_DIR variable from settings
    root_dir = Path(settings.ROOT_DIR)

    temp_dir = root_dir / 'temp'
    temp_dir.mkdir(exist_ok=True)  # Create 'temp' directory if it doesn't exist

    # Extract patient ID from the S3 key
    patient_id = Path(s3_key).parts[-2]  # Get the patient ID from the S3 key
    patient_temp_dir = temp_dir / patient_id
    patient_temp_dir.mkdir(exist_ok=True)  # Create patient-specific temp directory

    return patient_temp_dir

def delete_temp_directory(temp_dir: Path):
    """Delete the specified temporary directory."""
    if temp_dir.exists() and temp_dir.is_dir():

        shutil.rmtree(temp_dir)  # Remove the entire patient-specific temp directory
        logger.info(f"Deleted temporary directory: {temp_dir}")
