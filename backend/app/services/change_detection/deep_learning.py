import numpy as np
from typing import Dict, Any, Tuple
from app.services.change_detection.base import ChangeDetectionStrategy


class DeepLearningSegmentationStrategy(ChangeDetectionStrategy):
    """
    SNUNet-CD Deep Learning Change Detection Strategy.
    Powered by the trained EXP-02 Siamese Nested U-Net (7.79M parameters, base_width=32).

    Trained on remote sensing change detection datasets.
    Sentinel-2 inference is executed using 512x512 edge-aligned tiling with
    standardized RGB normalization (mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]).
    """

    def detect(
        self,
        historical_img: np.ndarray,
        recent_img: np.ndarray,
        parameters: Dict[str, Any]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        threshold = float(parameters.get("threshold", 0.30))

        try:
            from app.services.snunet_service import snunet_model_service

            probabilities = snunet_model_service.infer_probabilities(
                earlier=historical_img,
                later=recent_img,
                valid_mask=parameters.get("valid_data_mask"),
            )
            mask_bool = probabilities >= threshold
            binary_mask = (mask_bool.astype(np.uint8)) * 255

            changed_pixels = int(np.count_nonzero(mask_bool))
            total_pixels = int(binary_mask.size)
            pct = round((changed_pixels / total_pixels * 100.0), 3) if total_pixels else 0.0

            metadata = {
                "algorithm": "SNUNet-CD Deep Learning Change Detection",
                "model_architecture": "SNUNetCD (Nested Dense Channel Attention, base_width=32)",
                "checkpoint": "EXP-02 full_seed42_512_recovery_v2 epoch 10",
                "threshold": threshold,
                "changed_pixel_percentage": pct,
                "changed_pixels": changed_pixels,
                "total_pixels": total_pixels,
                "mean_probability": round(float(probabilities.mean()), 4),
                "max_probability": round(float(probabilities.max()), 4),
                "probability_map": probabilities,
                "status": "Inference Complete (Requires human & geospatial verification)",
                "version": "2.0.0-snunet-cd"
            }
            return binary_mask, metadata

        except Exception as exc:
            raise RuntimeError(
                f"SNUNet-CD inference failed; no substitute detections were generated: {exc}"
            ) from exc
