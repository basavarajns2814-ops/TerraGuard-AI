from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
from PIL import Image

from app.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHECKPOINT_PATH = (
    PROJECT_ROOT
    / "training"
    / "experiments"
    / "EXP-02_SNUNet"
    / "checkpoints"
    / "full_seed42_512_recovery_v2"
    / "best.pt"
)
DEFAULT_PATCH_SIZE = 512
DEFAULT_MEAN = (0.485, 0.456, 0.406)
DEFAULT_STD = (0.229, 0.224, 0.225)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


class SNUNetCDInferenceService:
    """Inference-only service for the EXP-02 SNUNet-CD checkpoint."""

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        model_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        self.checkpoint_path = str(checkpoint_path or os.environ.get(
            "SNUNET_CHECKPOINT_PATH",
            DEFAULT_CHECKPOINT_PATH,
        ))
        self.model_factory = model_factory
        self._model = None
        self._checkpoint = None
        self._device = None
        self._torch = None
        self._mean = np.asarray(DEFAULT_MEAN, dtype=np.float32)
        self._std = np.asarray(DEFAULT_STD, dtype=np.float32)
        self._base_width = 32
        self._epoch: Optional[int] = None
        self._threshold: Optional[float] = None
        self._patch_size = DEFAULT_PATCH_SIZE

    @property
    def model(self):
        self.initialize()
        return self._model

    @property
    def device(self):
        self.initialize()
        return self._device

    @property
    def epoch(self) -> Optional[int]:
        self.initialize()
        return self._epoch

    @property
    def threshold(self) -> float:
        self.initialize()
        return float(self._threshold if self._threshold is not None else 0.3)

    @property
    def normalization(self) -> dict:
        self.initialize()
        return {
            "mean": [round(float(value), 6) for value in self._mean],
            "std": [round(float(value), 6) for value in self._std],
        }

    def initialize(self) -> None:
        if self._model is not None:
            return

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "PyTorch is required for SNUNet-CD inference but is not installed."
            ) from exc

        self._torch = torch
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        checkpoint_path = Path(self.checkpoint_path)
        if not checkpoint_path.is_file():
            raise FileNotFoundError(
                f"SNUNet-CD checkpoint not found at: {checkpoint_path}"
            )

        checkpoint = torch.load(
            str(checkpoint_path),
            map_location=self._device,
            weights_only=True,
        )
        if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
            raise ValueError(
                "Invalid SNUNet-CD checkpoint: expected a model_state_dict entry."
            )

        if self.model_factory is None:
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            from training.snunet_model import SNUNetCD

            self.model_factory = SNUNetCD

        configuration = checkpoint.get("configuration", {})
        self._base_width = int(configuration.get("base_width", 32))
        self._epoch = checkpoint.get("epoch")
        self._threshold = checkpoint.get("threshold")
        self._patch_size = int(configuration.get("patch_size", DEFAULT_PATCH_SIZE))
        if self._patch_size <= 0:
            raise ValueError("SNUNet-CD checkpoint patch_size must be positive.")

        normalization = checkpoint.get("normalization", {})
        mean = normalization.get("mean", DEFAULT_MEAN)
        std = normalization.get("std", DEFAULT_STD)
        mean_array = np.asarray(mean, dtype=np.float32)
        std_array = np.asarray(std, dtype=np.float32)
        if mean_array.shape != (3,) or std_array.shape != (3,):
            raise ValueError("SNUNet-CD normalization must contain three mean and std values.")
        if np.any(~np.isfinite(mean_array)) or np.any(~np.isfinite(std_array)):
            raise ValueError("SNUNet-CD normalization contains non-finite values.")
        if np.any(std_array <= 0):
            raise ValueError("SNUNet-CD normalization std values must be positive.")
        self._mean = mean_array
        self._std = std_array

        model = self.model_factory(
            base_width=self._base_width,
            pretrained=False,
        )
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.to(self._device)
        model.eval()
        self._model = model
        self._checkpoint = checkpoint

    def validate_image_pair(
        self,
        earlier_path: str,
        later_path: str,
    ) -> Tuple[np.ndarray, np.ndarray, int, int]:
        for label, image_path in (("Earlier", earlier_path), ("Later", later_path)):
            if not os.path.isfile(image_path):
                raise FileNotFoundError(f"{label} satellite image not found at: {image_path}")
            extension = Path(image_path).suffix.lower()
            if extension and extension not in ALLOWED_IMAGE_EXTENSIONS:
                raise ValueError(
                    f"Unsupported {label.lower()} image format. "
                    "Allowed: JPG, JPEG, PNG, TIF, TIFF, BMP."
                )

        try:
            with Image.open(earlier_path) as image:
                earlier = np.asarray(image.convert("RGB"), dtype=np.uint8)
        except Exception as exc:
            raise ValueError(f"Unable to decode earlier image: {exc}") from exc

        try:
            with Image.open(later_path) as image:
                later = np.asarray(image.convert("RGB"), dtype=np.uint8)
        except Exception as exc:
            raise ValueError(f"Unable to decode later image: {exc}") from exc

        if earlier.shape != later.shape:
            raise ValueError(
                "Image dimension mismatch: earlier and later images must have "
                "identical width and height."
            )
        if earlier.ndim != 3 or earlier.shape[2] != 3:
            raise ValueError("Earlier and later images must decode as RGB images.")
        if earlier.shape[0] <= 0 or earlier.shape[1] <= 0:
            raise ValueError("Images must have positive width and height.")

        height, width = earlier.shape[:2]
        return earlier, later, width, height

    def preprocess_tile(
        self,
        earlier: np.ndarray,
        later: np.ndarray,
        valid_mask: Optional[np.ndarray] = None,
    ) -> Tuple[object, object]:
        """Convert paired RGB tiles using the checkpoint normalization."""
        self.initialize()

        earlier_tile = np.ascontiguousarray(earlier, dtype=np.float32).transpose(2, 0, 1) / 255.0
        later_tile = np.ascontiguousarray(later, dtype=np.float32).transpose(2, 0, 1) / 255.0
        mean = self._mean[:, None, None]
        std = self._std[:, None, None]
        earlier_tile = (earlier_tile - mean) / std
        later_tile = (later_tile - mean) / std

        tensor_a = self._torch.from_numpy(earlier_tile)[None].to(self._device)
        tensor_b = self._torch.from_numpy(later_tile)[None].to(self._device)
        if valid_mask is not None:
            if valid_mask.shape != earlier.shape[:2]:
                raise ValueError("Inference validity mask dimensions must match the input tile.")
            valid = self._torch.from_numpy(
                np.ascontiguousarray(valid_mask, dtype=bool)
            )[None, None].to(self._device)
            # Zero after normalization is the checkpoint mean reflectance and
            # prevents no-data values from presenting as artificial black pixels.
            tensor_a = tensor_a.masked_fill(~valid, 0.0)
            tensor_b = tensor_b.masked_fill(~valid, 0.0)
        return tensor_a, tensor_b

    def infer_probabilities(
        self,
        earlier: np.ndarray,
        later: np.ndarray,
        valid_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Run the model over non-overlapping edge-aligned 512-pixel tiles."""
        self.initialize()
        height, width = earlier.shape[:2]
        if earlier.shape != later.shape:
            raise ValueError("Earlier and later inference arrays must have identical dimensions.")
        if valid_mask is not None and valid_mask.shape != (height, width):
            raise ValueError("Inference validity mask dimensions must match the image pair.")
        probability_full = np.zeros((height, width), dtype=np.float32)

        with self._torch.inference_mode():
            for top in range(0, height, self._patch_size):
                bottom = min(top + self._patch_size, height)
                for left in range(0, width, self._patch_size):
                    right = min(left + self._patch_size, width)
                    tile_a, tile_b = self.preprocess_tile(
                        earlier[top:bottom, left:right],
                        later[top:bottom, left:right],
                        valid_mask[top:bottom, left:right] if valid_mask is not None else None,
                    )
                    if self._device.type == "cuda":
                        with self._torch.autocast(
                            device_type="cuda",
                            dtype=self._torch.float16,
                            enabled=True,
                        ):
                            logits = self._model(tile_a, tile_b)
                    else:
                        logits = self._model(tile_a, tile_b)
                    probability = self._torch.sigmoid(logits.float())[0, 0]
                    probability_full[top:bottom, left:right] = (
                        probability.detach().cpu().numpy()
                    )

        if valid_mask is not None:
            probability_full[~valid_mask] = 0.0

        return np.ascontiguousarray(probability_full, dtype=np.float32)

    def run_prediction(
        self,
        earlier_path: str,
        later_path: str,
        threshold: Optional[float] = None,
    ) -> dict:
        if threshold is not None and not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("Prediction threshold must be between 0 and 1.")

        earlier, later, width, height = self.validate_image_pair(
            earlier_path,
            later_path,
        )
        probabilities = self.infer_probabilities(earlier, later)
        selected_threshold = self.threshold if threshold is None else float(threshold)
        mask_bool = probabilities >= selected_threshold
        mask_uint8 = mask_bool.astype(np.uint8) * 255

        overlay = np.array(later, dtype=np.uint8, copy=True)
        overlay[mask_bool] = (
            overlay[mask_bool] * 0.45
            + np.asarray((255, 0, 0), dtype=np.float32) * 0.55
        ).round().clip(0, 255).astype(np.uint8)
        probability_uint8 = np.rint(probabilities * 255.0).clip(0, 255).astype(np.uint8)

        mask_dir = Path(settings.STORAGE_DIR) / "masks"
        mask_dir.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:10]
        probability_filename = f"snunet_probability_{token}.png"
        mask_filename = f"snunet_mask_{token}.png"
        overlay_filename = f"snunet_overlay_{token}.png"

        Image.fromarray(probability_uint8, mode="L").save(mask_dir / probability_filename)
        Image.fromarray(mask_uint8, mode="L").save(mask_dir / mask_filename)
        Image.fromarray(overlay, mode="RGB").save(mask_dir / overlay_filename)

        total_pixels = width * height
        changed_pixels = int(np.count_nonzero(mask_bool))
        changed_percentage = (
            round(changed_pixels / total_pixels * 100.0, 3)
            if total_pixels
            else 0.0
        )

        return {
            "model_name": "EXP-02 SNUNet-CD",
            "model_type": "SNUNet-CD-nested-dense-channel-attention-v1",
            "architecture": "SNUNetCD",
            "checkpoint_path": str(Path(self.checkpoint_path).resolve()),
            "epoch": int(self.epoch) if self.epoch is not None else None,
            "threshold": selected_threshold,
            "normalization": self.normalization,
            "patch_size": self._patch_size,
            "dimensions": {
                "width": width,
                "height": height,
                "channels": 3,
            },
            "total_pixels": total_pixels,
            "changed_pixels": changed_pixels,
            "changed_pixel_percentage": changed_percentage,
            "mean_probability": round(float(probabilities.mean()), 4),
            "max_probability": round(float(probabilities.max()), 4),
            "min_probability": round(float(probabilities.min()), 4),
            "probability_url": f"/storage/masks/{probability_filename}",
            "mask_url": f"/storage/masks/{mask_filename}",
            "overlay_url": f"/storage/masks/{overlay_filename}",
            "probabilities": probabilities,
            "mask_bool": mask_bool,
            "mask_uint8": mask_uint8,
            "disclaimer": (
                "SNUNet-CD image-change output does not establish legal or physical "
                "encroachment. Results require human and geospatial verification."
            ),
        }


snunet_model_service = SNUNetCDInferenceService()
