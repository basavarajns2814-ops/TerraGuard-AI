"""A transparent, non-trained pixel-difference change-detection baseline."""

from __future__ import annotations

import numpy as np


def predict_change(image_a: np.ndarray, image_b: np.ndarray, threshold: int) -> np.ndarray:
    """Return pixels whose mean absolute RGB difference exceeds threshold."""
    if image_a.shape != image_b.shape:
        raise ValueError(f"Images must have matching shapes, got {image_a.shape} and {image_b.shape}.")
    if image_a.ndim != 3 or image_a.shape[2] != 3:
        raise ValueError("Both input images must be RGB arrays.")
    if not 0 <= threshold <= 255:
        raise ValueError("Threshold must be between 0 and 255.")

    difference = np.abs(image_a.astype(np.int16) - image_b.astype(np.int16)).mean(axis=2)
    return difference > threshold


def make_overlay(image: np.ndarray, predicted_mask: np.ndarray) -> np.ndarray:
    """Tint predicted pixels red on a copy of the later image."""
    if image.ndim != 3 or image.shape[2] != 3 or image.shape[:2] != predicted_mask.shape:
        raise ValueError("The RGB image and predicted mask must have matching spatial dimensions.")

    overlay = image.copy()
    tint = np.array([255, 55, 70], dtype=np.float32)
    overlay[predicted_mask] = (
        overlay[predicted_mask].astype(np.float32) * 0.45 + tint * 0.55
    ).astype(np.uint8)
    return overlay
