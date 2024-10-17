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
    
    # The rest of the code is unchanged, using local_file_path
    axial_slice, coronal_slice, sagittal_slice = get_middle_slices(local_file_path)

    axial_input = preprocess_slice(axial_slice)
    coronal_input = preprocess_slice(coronal_slice)
    sagittal_input = preprocess_slice(sagittal_slice)

    logger.info("Making predictions for axial, coronal, and sagittal slices.")
    axial_prediction = axial_model.predict(axial_input)
    coronal_prediction = coronal_model.predict(coronal_input)
    sagittal_prediction = sagittal_model.predict(sagittal_input)

    result = ensemble_predictions(axial_prediction, coronal_prediction, sagittal_prediction)
    logger.info(f"Prediction result: {result}")
    return result


def rescale_slice(slice_data):
    logger.info("Rescaling slice data to [0, 1] range.")
    slice_data = slice_data.astype(np.float32)
    slice_data = slice_data / 255.0
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


def get_middle_slices(nii_file_path):
    logger.info(f"Loading MRI file: {nii_file_path}")
    nii_image = nib.load(nii_file_path)
    nii_data = nii_image.get_fdata()

    affine = nii_image.affine
    plane_to_axis = determine_axes(affine)

    logger.info(
        "Extracting middle slices from axial, coronal, and sagittal planes.")
    mid_axial = nii_data.shape[plane_to_axis['S']] // 2
    mid_coronal = nii_data.shape[plane_to_axis['A']] // 2
    mid_sagittal = nii_data.shape[plane_to_axis['R']] // 2

    axial_slice = np.take(nii_data, mid_axial, axis=plane_to_axis['S'])
    coronal_slice = np.take(nii_data, mid_coronal, axis=plane_to_axis['A'])
    sagittal_slice = np.take(nii_data, mid_sagittal, axis=plane_to_axis['R'])

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
