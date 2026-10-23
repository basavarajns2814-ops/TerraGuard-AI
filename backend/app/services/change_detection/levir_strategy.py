import sys
import os
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np

# Ensure backend root is in sys.path so ml and src imports resolve cleanly
backend_root = Path(__file__).resolve().parent.parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.services.change_detection.base import ChangeDetectionStrategy
from ml.levir_model import load_classifier, predict_probability, FEATURE_SCHEMA

class LevirCdChangeDetectionStrategy(ChangeDetectionStrategy):
    """
    Trained LEVIR-CD+ Building Change Detection Strategy using HistGradientBoostingClassifier.
    Utilizes 10-feature schema: rgb_pair_abs_difference_local_mean_v1.
    """
    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = os.path.join(str(backend_root), "models", "levir_change_model.joblib")
        self.model_path = model_path
        self._artifact = None

    @property
    def artifact(self) -> Dict[str, Any]:
        if self._artifact is None:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"LEVIR-CD+ model artifact not found at {self.model_path}")
            self._artifact = load_classifier(self.model_path)
        return self._artifact

    def detect(
        self,
        historical_img: np.ndarray,
        recent_img: np.ndarray,
        parameters: Dict[str, Any]
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        # Ensure dimensions match
        if historical_img.shape != recent_img.shape or historical_img.ndim != 3 or historical_img.shape[2] != 3:
            # Rescale if needed
            from PIL import Image
            h_h, h_w = historical_img.shape[:2]
            r_pil = Image.fromarray(recent_img).convert('RGB').resize((h_w, h_h), Image.Resampling.BILINEAR)
            recent_img = np.array(r_pil)

        threshold = float(parameters.get("threshold", self.artifact.get("threshold", 0.7)))

        # Predict probability map using original LEVIR-CD+ feature extraction pipeline
        probabilities = predict_probability(self.artifact, historical_img, recent_img)
        binary_mask_bool = probabilities >= threshold
        binary_mask_uint8 = binary_mask_bool.astype(np.uint8) * 255

        total_pixels = probabilities.size
        changed_pixels = int(np.count_nonzero(binary_mask_bool))
        changed_percentage = round((changed_pixels / total_pixels) * 100.0, 3) if total_pixels else 0.0

        metadata = {
            "algorithm": "LEVIR-CD+ Trained Building Classifier (HistGradientBoosting)",
            "model_type": "HistGradientBoostingClassifier",
            "feature_schema": FEATURE_SCHEMA,
            "threshold_applied": threshold,
            "changed_pixels": changed_pixels,
            "changed_pixel_percentage": changed_percentage,
            "mean_probability": round(float(probabilities.mean()), 4),
            "max_probability": round(float(probabilities.max()), 4),
            "min_probability": round(float(probabilities.min()), 4),
            "verification_notice": "Potential building change candidates require human verification before confirming encroachment."
        }

        return binary_mask_uint8, metadata
