from pathlib import Path

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
import app.routers.analysis as analysis_router
from app.services.snunet_service import (
    DEFAULT_CHECKPOINT_PATH,
    SNUNetCDInferenceService,
)


class DeterministicFixtureModel(torch.nn.Module):
    def __init__(self, base_width=32, pretrained=False):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.zeros(1))

    def load_state_dict(self, state_dict, strict=True):
        return super().load_state_dict(state_dict, strict=strict)

    def forward(self, image_a, image_b):
        height, width = image_a.shape[-2:]
        return self.weight.reshape(1, 1, 1, 1) + torch.ones(
            (image_a.shape[0], 1, height, width),
            dtype=image_a.dtype,
            device=image_a.device,
        ) * -0.25


@pytest.fixture
def fixture_checkpoint(tmp_path):
    checkpoint = tmp_path / "fixture.pt"
    model = DeterministicFixtureModel()
    torch.save(
        {
            "architecture": "SNUNet-CD-nested-dense-channel-attention-v1",
            "epoch": 3,
            "threshold": 0.6,
            "model_state_dict": model.state_dict(),
            "normalization": {
                "mean": [0.1, 0.2, 0.3],
                "std": [0.4, 0.5, 0.6],
            },
            "configuration": {"base_width": 32, "patch_size": 512},
        },
        checkpoint,
    )
    return checkpoint


def make_image_pair(tmp_path, width, height):
    earlier = tmp_path / "earlier.png"
    later = tmp_path / "later.png"
    Image.new("RGB", (width, height), (20, 40, 60)).save(earlier)
    Image.new("RGB", (width, height), (220, 180, 140)).save(later)
    return earlier, later


def test_actual_exp02_checkpoint_loads_and_reports_epoch_ten():
    service = SNUNetCDInferenceService(checkpoint_path=str(DEFAULT_CHECKPOINT_PATH))
    service.initialize()
    assert service._epoch == 10
    assert service.threshold == 0.3
    assert service.normalization == {
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
    }
    assert sum(parameter.numel() for parameter in service.model.parameters()) == 7_791_309


def test_fixture_checkpoint_reads_custom_normalization(fixture_checkpoint):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    service.initialize()
    assert service.normalization == {
        "mean": [0.1, 0.2, 0.3],
        "std": [0.4, 0.5, 0.6],
    }
    assert service.epoch == 3
    assert service.threshold == 0.6


def test_preprocessing_uses_checkpoint_normalization(fixture_checkpoint):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    red = np.full((2, 2, 3), [255, 128, 0], dtype=np.uint8)
    tile_a, tile_b = service.preprocess_tile(red, red)
    expected_a = torch.tensor([[(255 / 255 - 0.1) / 0.4]], dtype=torch.float32)
    assert torch.allclose(
        tile_a[0, 0, 0, 0],
        expected_a[0, 0],
        atol=1e-6,
    )
    assert tile_a.shape == (1, 3, 2, 2)
    assert tile_b.shape == tile_a.shape


@pytest.mark.parametrize("size", [300, 512, 900])
def test_matching_sizes_reconstruct_original_dimensions(tmp_path, fixture_checkpoint, size):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    earlier, later = make_image_pair(tmp_path, size, size)
    earlier_array, later_array, width, height = service.validate_image_pair(
        str(earlier),
        str(later),
    )
    probabilities = service.infer_probabilities(earlier_array, later_array)
    assert probabilities.shape == (height, width) == (size, size)
    assert np.isfinite(probabilities).all()
    assert probabilities.min() >= 0
    assert probabilities.max() <= 1


def test_mismatched_and_invalid_images_are_rejected(tmp_path, fixture_checkpoint):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    earlier, _ = make_image_pair(tmp_path, 300, 300)
    mismatched = tmp_path / "mismatched.png"
    Image.new("RGB", (301, 300), (0, 0, 0)).save(mismatched)
    with pytest.raises(ValueError, match="dimension mismatch"):
        service.validate_image_pair(str(earlier), str(mismatched))

    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="Unable to decode earlier image"):
        service.validate_image_pair(str(invalid), str(earlier))


def test_threshold_validation_and_artifact_generation(tmp_path, fixture_checkpoint):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    earlier, later = make_image_pair(tmp_path, 700, 300)

    with pytest.raises(ValueError, match="between 0 and 1"):
        service.run_prediction(str(earlier), str(later), threshold=1.1)

    result = service.run_prediction(str(earlier), str(later), threshold=0.5)
    assert result["dimensions"] == {"width": 700, "height": 300, "channels": 3}
    assert result["total_pixels"] == 700 * 300
    assert result["epoch"] == 3
    assert result["threshold"] == 0.5
    assert result["probability_url"].startswith("/storage/masks/snunet_probability_")
    assert result["mask_url"].startswith("/storage/masks/snunet_mask_")
    assert result["overlay_url"].startswith("/storage/masks/snunet_overlay_")
    assert "encroachment" in result["disclaimer"].lower()

    storage_root = Path(settings.STORAGE_DIR)
    for artifact_key in ("probability_url", "mask_url", "overlay_url"):
        artifact_path = storage_root / result[artifact_key].removeprefix("/storage/")
        assert artifact_path.is_file()
        with Image.open(artifact_path) as artifact:
            if artifact_key == "mask_url":
                assert artifact.size == (700, 300)
            if artifact_key == "overlay_url":
                assert artifact.mode == "RGB"
                assert artifact.size == (700, 300)


def test_real_epoch10_checkpoint_runs_real_image_pair(tmp_path):
    service = SNUNetCDInferenceService(checkpoint_path=str(DEFAULT_CHECKPOINT_PATH))
    earlier, later = make_image_pair(tmp_path, 512, 512)
    result = service.run_prediction(str(earlier), str(later), threshold=0.3)
    assert result["epoch"] == 10
    assert result["dimensions"] == {"width": 512, "height": 512, "channels": 3}
    assert result["probabilities"].shape == (512, 512)
    assert np.isfinite(result["probabilities"]).all()
    assert result["mask_bool"].shape == (512, 512)


def test_api_requires_authentication_and_returns_response(monkeypatch, fixture_checkpoint, tmp_path):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    monkeypatch.setattr(analysis_router, "snunet_model_service", service)

    earlier, later = make_image_pair(tmp_path, 300, 300)
    with TestClient(app) as client:
        with earlier.open("rb") as earlier_file, later.open("rb") as later_file:
            unauthenticated = client.post(
                "/api/analysis/snunet/predict-upload",
                files={
                    "earlier_file": ("earlier.png", earlier_file, "image/png"),
                    "later_file": ("later.png", later_file, "image/png"),
                },
            )
        assert unauthenticated.status_code == 401

        login = client.post(
            "/api/auth/login",
            json={
                "email": "officer@terraguard.gov.in",
                "password": "Officer@123",
            },
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        with earlier.open("rb") as earlier_file, later.open("rb") as later_file:
            response = client.post(
                "/api/analysis/snunet/predict-upload",
                headers=headers,
                files={
                    "earlier_file": ("earlier.png", earlier_file, "image/png"),
                    "later_file": ("later.png", later_file, "image/png"),
                },
                data={"threshold": "0.5"},
            )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["model_name"] == "EXP-02 SNUNet-CD"
        assert result["epoch"] == 3
        assert result["threshold"] == 0.5
        assert result["dimensions"] == {"width": 300, "height": 300, "channels": 3}
        assert {"probability_url", "mask_url", "overlay_url"} <= result.keys()
        assert "encroachment" in result["disclaimer"].lower()


def test_api_rejects_mismatched_dimensions(monkeypatch, fixture_checkpoint, tmp_path):
    service = SNUNetCDInferenceService(
        checkpoint_path=str(fixture_checkpoint),
        model_factory=DeterministicFixtureModel,
    )
    monkeypatch.setattr(analysis_router, "snunet_model_service", service)
    earlier, _ = make_image_pair(tmp_path, 300, 300)
    mismatched = tmp_path / "mismatched.png"
    Image.new("RGB", (301, 300), (0, 0, 0)).save(mismatched)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "officer@terraguard.gov.in",
                "password": "Officer@123",
            },
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        with earlier.open("rb") as earlier_file, mismatched.open("rb") as later_file:
            response = client.post(
                "/api/analysis/snunet/predict-upload",
                headers=headers,
                files={
                    "earlier_file": ("earlier.png", earlier_file, "image/png"),
                    "later_file": ("later.png", later_file, "image/png"),
                },
            )
    assert response.status_code == 400
    assert "dimension mismatch" in response.json()["detail"]
