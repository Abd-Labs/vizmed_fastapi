import cv2
import numpy as np
import logging
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def create_tissue_mask(mri_image: np.ndarray) -> np.ndarray:
    """Create a mask for non-background (tissue) areas of the MRI image."""
    _, tissue_mask = cv2.threshold(mri_image, 10, 255, cv2.THRESH_BINARY)
    logger.info("Tissue mask created for MRI image")
    return tissue_mask

def apply_kmeans_clustering(mri_image: np.ndarray, clusters: int = 4) -> tuple:
    """Apply K-means clustering to the MRI image."""
    pixel_values = mri_image.reshape((-1, 1)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(pixel_values, clusters, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    logger.info(f"K-means clustering applied with {clusters} clusters")
    return labels, centers

def resize_color_spectrum(color_spectrum: np.ndarray, clusters: int) -> np.ndarray:
    """Resize the color spectrum to match the number of clusters."""
    color_spectrum_resized = cv2.resize(color_spectrum, (clusters, 1))
    logger.info(f"Color spectrum resized to {clusters} clusters")
    return color_spectrum_resized

def map_colors_to_clusters(labels: np.ndarray, centers: np.ndarray, mri_image_shape: tuple) -> np.ndarray:
    """Map each pixel to its cluster center to create a segmented image."""
    segmented_image = centers[labels.flatten()].reshape(mri_image_shape)
    logger.info("Cluster centers mapped to MRI image")
    return segmented_image

def apply_colorization(segmented_image: np.ndarray, tissue_mask: np.ndarray, color_spectrum: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Apply colors to the MRI image based on cluster labels and the color spectrum."""
    clusters = color_spectrum.shape[1]
    colorized_image = np.zeros((*segmented_image.shape, 3), dtype=np.uint8)
    for i in range(clusters):
        color = color_spectrum[0, i]
        colorized_image[(segmented_image == centers[i]) & (tissue_mask == 255)] = color
    logger.info("MRI image colorization completed successfully")
    return colorized_image

def colorize_mri_image(mri_image: np.ndarray, color_spectrum: np.ndarray, clusters: int = 4) -> np.ndarray:
    """Main function to colorize an MRI image."""
    tissue_mask = create_tissue_mask(mri_image)
    labels, centers = apply_kmeans_clustering(mri_image, clusters)
    color_spectrum_resized = resize_color_spectrum(color_spectrum, clusters)
    segmented_image = map_colors_to_clusters(labels, centers, mri_image.shape)
    return apply_colorization(segmented_image, tissue_mask, color_spectrum_resized, centers)
