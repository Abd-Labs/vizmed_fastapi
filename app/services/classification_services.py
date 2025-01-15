import nibabel as nib
import numpy as np
import cv2
from tensorflow.keras.models import load_model
from tensorflow.keras.utils import get_custom_objects
import tensorflow_addons as tfa
from app.core.config import settings
from app.services.s3 import download_file_from_s3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load models at the start to avoid reloading them for every request
logger.info("Loading pretrained models...")
get_custom_objects().update({'Addons>F1Score': tfa.metrics.F1Score})

try:
    axial_model = load_model(settings.AXIAL_MODEL_PATH)
    logger.info("Axial model loaded successfully.")

    coronal_model = load_model(settings.CORONAL_MODEL_PATH)
    logger.info("Coronal model loaded successfully.")

    sagittal_model = load_model(settings.SAGITTAL_MODEL_PATH)
    logger.info("Sagittal model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load models: {e}")
    raise e


def classify_mri_file(s3_key: str, bucket_name: str, local_file_path):

    # Check if the file exists locally
    if not os.path.isfile(local_file_path):
        logger.info(f"File not found locally. Downloading from S3: {s3_key}")
        download_file_from_s3(s3_key, bucket_name, local_file_path)

    logger.info(f"Classifying MRI file: {local_file_path}")

    # Extract middle slices with consistent orientation
    axial_slice, coronal_slice, sagittal_slice = get_middle_slices(
        local_file_path)

    # Preprocess slices for classification
    axial_input = preprocess_slice(axial_slice)
    coronal_input = preprocess_slice(coronal_slice)
    sagittal_input = preprocess_slice(sagittal_slice)

    logger.info("Making predictions for axial, coronal, and sagittal slices.")
    axial_prediction = axial_model.predict(axial_input)
    coronal_prediction = coronal_model.predict(coronal_input)
    sagittal_prediction = sagittal_model.predict(sagittal_input)

    # Get class labels as strings
    axial_class_label = get_class_label(axial_prediction)
    coronal_class_label = get_class_label(coronal_prediction)
    sagittal_class_label = get_class_label(sagittal_prediction)

    # Ensemble predictions from all planes
    ensemble_result = ensemble_predictions(
        axial_prediction, coronal_prediction, sagittal_prediction)

    result = {
        "axial_classification": axial_class_label,
        "coronal_classification": coronal_class_label,
        "sagittal_classification": sagittal_class_label,
        "ensemble_prediction": ensemble_result
    }

    logger.info(f"Prediction result: {result}")

    return result


def rescale_slice(slice_data):
    logger.info("Rescaling slice data to [0, 1] range.")
    slice_data = slice_data.astype(np.float32)
    slice_data = slice_data / np.max(slice_data)
    return slice_data


def determine_axes(affine):
    logger.info("Determining the axes for slice extraction.")
    orientation = nib.aff2axcodes(affine)
    plane_to_axis = {'R': None, 'A': None, 'S': None}
    for idx, axis in enumerate(orientation):
        if axis in ('R', 'L'):
            plane_to_axis['R'] = idx  # Sagittal
        elif axis in ('A', 'P'):
            plane_to_axis['A'] = idx  # Coronal
        elif axis in ('S', 'I'):
            plane_to_axis['S'] = idx  # Axial
    logger.info(f"Axes determined: {plane_to_axis}")
    return plane_to_axis


def reorient_to_ras(nii_image):
    """Reorient NIfTI data to RAS standard."""
    data = nii_image.get_fdata()
    shape = data.shape

    if len(shape) < 3:
        # Skip reorientation if the data is not 3D
        logger.warning("Data is not 3D. Skipping reorientation.")
        return data, None

    # Reorient to RAS if the data is 3D
    ras_orientation = nib.orientations.io_orientation(nii_image.affine)
    ras_transform = nib.orientations.ornt_transform(
        ras_orientation, nib.orientations.axcodes2ornt(("R", "A", "S")))
    reoriented_data = nib.orientations.apply_orientation(data, ras_transform)

    return reoriented_data, ras_orientation


def get_middle_slices(nii_file_path):
    logger.info(f"Loading and reorienting MRI file: {nii_file_path}")
    nii_image = nib.load(nii_file_path)
    data, _ = reorient_to_ras(nii_image)

    if len(data.shape) < 3:
        logger.warning("Data is 2D. Using the single slice for all views.")
        return data, data, data

    # Extract middle slices for 3D data
    mid_axial = data.shape[2] // 2
    mid_coronal = data.shape[1] // 2
    mid_sagittal = data.shape[0] // 2

    axial_slice = np.rot90(data[:, :, mid_axial])
    coronal_slice = np.rot90(data[:, mid_coronal, :])
    sagittal_slice = np.rot90(data[mid_sagittal, :, :])

    return axial_slice, coronal_slice, sagittal_slice


def preprocess_slice(slice_data):
    logger.info("Preprocessing MRI slice for model input.")
    slice_data = rescale_slice(slice_data)
    slice_data_resized = cv2.resize(slice_data, (128, 128))
    slice_data_rgb = np.stack([slice_data_resized] * 3, axis=-1)
    slice_data_rgb = np.expand_dims(slice_data_rgb, axis=0)
    return slice_data_rgb


def get_class_label(prediction):
    logger.info("Mapping prediction to class label.")
    class_labels = ['AD', 'CN', 'EMCI', 'LMCI', 'MCI']  # Assuming 5 classes
    return class_labels[np.argmax(prediction)]


def ensemble_predictions(axial_pred, coronal_pred, sagittal_pred):
    logger.info("Averaging predictions from all three planes.")
    ensemble_pred = (axial_pred + coronal_pred + sagittal_pred) / 3.0
    return get_class_label(ensemble_pred)
