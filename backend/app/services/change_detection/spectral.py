import numpy as np
from typing import Dict, Any, Tuple
from app.services.change_detection.base import ChangeDetectionStrategy

class SpectralChangeDetection(ChangeDetectionStrategy):
    """
    Computes spectral index differences (NDVI vegetation index, NDBI/Brightness built-up index)
    or image difference thresholding for RGB / multi-band satellite images.
    """
    def detect(
        self,
        historical_img: np.ndarray,
        recent_img: np.ndarray,
        parameters: Dict[str, Any]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        # Ensure floating point representation [0.0, 1.0]
        h_norm = historical_img.astype(np.float32) / 255.0
        r_norm = recent_img.astype(np.float32) / 255.0

        h_h, h_w = h_norm.shape[:2]
        r_h, r_w = r_norm.shape[:2]

        # Rescale if dimensions slightly differ
        if (h_h, h_w) != (r_h, r_w):
            from PIL import Image
            r_pil = Image.fromarray((r_norm * 255).astype(np.uint8))
            r_pil = r_pil.resize((h_w, h_h))
            r_norm = np.array(r_pil).astype(np.float32) / 255.0

        threshold = parameters.get("threshold", 0.18)

        # Check channel count
        channels = h_norm.shape[2] if len(h_norm.shape) == 3 else 1

        if channels >= 3:
            # RGB channels: Red = 0, Green = 1, Blue = 2
            # Compute VARI (Visible Atmospherically Resistant Index) as optical vegetation proxy:
            # VARI = (Green - Red) / (Green + Red - Blue + 1e-5)
            h_vari = (h_norm[:, :, 1] - h_norm[:, :, 0]) / (h_norm[:, :, 1] + h_norm[:, :, 0] - h_norm[:, :, 2] + 1e-4)
            r_vari = (r_norm[:, :, 1] - r_norm[:, :, 0]) / (r_norm[:, :, 1] + r_norm[:, :, 0] - r_norm[:, :, 2] + 1e-4)

            # Vegetation drop: historical greenness minus recent greenness
            veg_loss = h_vari - r_vari
            veg_loss_mask = (veg_loss > threshold).astype(np.uint8)

            # Gray-scale brightness differencing (for new structures, roads, clearing)
            h_gray = 0.299 * h_norm[:, :, 0] + 0.587 * h_norm[:, :, 1] + 0.114 * h_norm[:, :, 2]
            r_gray = 0.299 * r_norm[:, :, 0] + 0.587 * r_norm[:, :, 1] + 0.114 * r_norm[:, :, 2]
            diff = np.abs(r_gray - h_gray)
            struct_mask = (diff > threshold).astype(np.uint8)

            combined_binary = np.clip(veg_loss_mask + struct_mask, 0, 1) * 255
            mean_change = float(np.mean(diff))
            max_change = float(np.max(diff))
        else:
            diff = np.abs(r_norm - h_norm)
            combined_binary = (diff > threshold).astype(np.uint8) * 255
            mean_change = float(np.mean(diff))
            max_change = float(np.max(diff))

        metadata = {
            "algorithm": "Spectral & Optical Differencing (VARI & Brightness)",
            "mean_pixel_difference": round(mean_change, 4),
            "max_pixel_difference": round(max_change, 4),
            "threshold_applied": threshold,
            "version": "1.0.0-baseline"
        }

        return combined_binary.astype(np.uint8), metadata
