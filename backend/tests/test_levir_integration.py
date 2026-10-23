from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

from app.main import app
from app.services.levir_service import levir_model_service


def test_levir_prediction_upload_returns_model_artifacts(tmp_path):
    project_root = Path(__file__).resolve().parents[2]
    earlier_path = tmp_path / "earlier.png"
    later_path = tmp_path / "later.png"
    earlier_image = Image.new("RGB", (128, 128), (45, 100, 55))
    later_image = earlier_image.copy()
    from PIL import ImageDraw

    ImageDraw.Draw(earlier_image).rectangle((30, 35, 75, 80), fill=(55, 115, 60))
    ImageDraw.Draw(later_image).rectangle((30, 35, 75, 80), fill=(220, 220, 225))
    earlier_image.save(earlier_path)
    later_image.save(later_path)

    assert Path(levir_model_service.model_path).resolve() == (
        project_root / "backend" / "models" / "levir_change_model.joblib"
    ).resolve()
    earlier = np.asarray(Image.open(earlier_path).convert("RGB"))
    later = np.asarray(Image.open(later_path).convert("RGB"))
    direct = levir_model_service.artifact
    from ml.levir_model import predict_probability

    probability = predict_probability(direct, earlier, later)
    assert probability.shape == earlier.shape[:2]
    assert np.isfinite(probability).all()

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "officer@terraguard.gov.in", "password": "Officer@123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        with earlier_path.open("rb") as earlier_file, later_path.open("rb") as later_file:
            response = client.post(
                "/api/analysis/levir/predict-upload",
                headers=headers,
                files={
                    "earlier_file": (earlier_path.name, earlier_file, "image/png"),
                    "later_file": (later_path.name, later_file, "image/png"),
                },
                data={"threshold": "0.7"},
            )

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["model_type"] == "HistGradientBoostingClassifier"
        assert result["feature_schema"] == "rgb_pair_abs_difference_local_mean_v1"
        assert result["total_pixels"] == earlier.shape[0] * earlier.shape[1]
        assert 0 <= result["changed_pixels"] <= result["total_pixels"]
        assert 0 <= result["changed_pixel_percentage"] <= 100
        assert "Potential building changes" in result["disclaimer"]
        for artifact_url in (result["mask_url"], result["overlay_url"]):
            artifact_response = client.get(artifact_url)
            assert artifact_response.status_code == 200
            assert artifact_response.headers["content-type"] == "image/png"

        # Keep the integration test from accumulating generated imagery artifacts.
        storage_root = project_root / "backend" / "storage"
        for artifact_url in (
            result["earlier_image_url"],
            result["later_image_url"],
            result["mask_url"],
            result["overlay_url"],
        ):
            artifact_path = storage_root / artifact_url.removeprefix("/storage/")
            artifact_path.unlink(missing_ok=True)
