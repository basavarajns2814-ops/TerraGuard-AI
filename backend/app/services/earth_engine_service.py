import hashlib
import io
import os
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from shapely.geometry import shape, mapping

from app.config import settings


DATASET = "COPERNICUS/S2_SR_HARMONIZED"
NODATA_VALUE = -9999.0


class EarthEngineConfigurationError(RuntimeError):
    pass


class EarthEngineCollectionEmptyError(RuntimeError):
    pass


class EarthEngineRequestError(RuntimeError):
    pass


class EarthEngineService:
    def __init__(self, ee_module=None, storage_dir: Optional[str] = None, session=None):
        self._ee = ee_module
        self._initialized = False
        self._auth_mode: Optional[str] = None
        self.storage_dir = storage_dir or settings.STORAGE_DIR
        self.output_dir = os.path.join(self.storage_dir, "earth_engine")
        os.makedirs(self.output_dir, exist_ok=True)
        self.session = session or requests.Session()

    def _get_ee(self):
        if self._ee is not None:
            return self._ee
        try:
            import ee
            self._ee = ee
            return ee
        except ImportError as exc:
            raise EarthEngineConfigurationError(
                "earthengine-api is not installed. Install backend requirements."
            ) from exc

    def initialize(self):
        if self._initialized:
            return {"initialized": True, "authentication": self._auth_mode}

        ee = self._get_ee()
        project_id = settings.GEE_PROJECT_ID
        if not project_id:
            raise EarthEngineConfigurationError(
                "GEE_PROJECT_ID is required. Configure a Google Cloud project ID."
            )

        try:
            key_file = settings.GEE_SERVICE_ACCOUNT_KEY_FILE
            if key_file:
                if not os.path.isfile(key_file):
                    raise EarthEngineConfigurationError(
                        f"GEE service-account key file not found: {key_file}"
                    )
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(
                    key_file,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-platform",
                        "https://www.googleapis.com/auth/earthengine.readonly",
                    ],
                )
                ee.Initialize(credentials=credentials, project=project_id)
                self._auth_mode = "service_account"
            else:
                ee.Initialize(project=project_id)
                self._auth_mode = "application_default_or_interactive"
            self._initialized = True
            return {"initialized": True, "authentication": self._auth_mode}
        except EarthEngineConfigurationError:
            raise
        except Exception as exc:
            raise EarthEngineConfigurationError(
                f"Google Earth Engine initialization failed: {exc}"
            ) from exc

    def health(self):
        try:
            result = self.initialize()
            return {
                "status": "configured" if result["initialized"] else "unavailable",
                "dataset": DATASET,
                "authentication": result["authentication"],
                "project_id": settings.GEE_PROJECT_ID,
            }
        except EarthEngineConfigurationError as exc:
            return {
                "status": "unavailable",
                "dataset": DATASET,
                "authentication": "not_configured",
                "project_id": settings.GEE_PROJECT_ID,
                "error": str(exc),
            }

    @staticmethod
    def validate_date_range(start_date: str, end_date: str):
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Dates must use ISO YYYY-MM-DD format.") from exc
        if start > end:
            raise ValueError("Start date must be on or before end date.")
        return start, end

    @staticmethod
    def validate_geometry(geometry: Any):
        if not isinstance(geometry, dict):
            raise ValueError("Monitoring geometry must be a GeoJSON object.")
        if geometry.get("type") == "Feature":
            geometry = geometry.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError("Monitoring geometry Feature has no geometry object.")
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Monitoring geometry must be a Polygon or MultiPolygon.")
        try:
            geom = shape(geometry)
            if geom.is_empty or not geom.is_valid:
                raise ValueError("Monitoring geometry is empty or invalid.")
        except Exception as exc:
            raise ValueError(f"Invalid monitoring geometry: {exc}") from exc
        return mapping(geom)

    @staticmethod
    def validate_request(
        start_date: str,
        end_date: str,
        max_cloud_coverage: float,
        width: int,
        height: int,
        resolution_meters: int,
    ):
        EarthEngineService.validate_date_range(start_date, end_date)
        if not 0 <= max_cloud_coverage <= 100:
            raise ValueError("Cloud coverage threshold must be between 0 and 100.")
        if not 256 <= width <= 4096 or not 256 <= height <= 4096:
            raise ValueError("Image dimensions must be between 256 and 4096 pixels.")
        if resolution_meters not in {10, 20, 60}:
            raise ValueError("Resolution must be 10, 20 or 60 metres.")

    @staticmethod
    def utm_crs_for_geometry(geometry: Dict[str, Any]) -> str:
        """Choose the local WGS84 UTM zone containing the monitoring centroid."""
        geom = shape(geometry)
        longitude, latitude = geom.centroid.x, geom.centroid.y
        zone = min(60, max(1, int((longitude + 180.0) // 6.0) + 1))
        epsg_base = 32600 if latitude >= 0 else 32700
        return f"EPSG:{epsg_base + zone}"

    @staticmethod
    def snap_bounds_to_grid(
        bounds: tuple[float, float, float, float], resolution_meters: int
    ) -> Dict[str, Any]:
        """Snap projected bounds outward and return a north-up affine grid."""
        import math

        min_x, min_y, max_x, max_y = bounds
        if not all(map(math.isfinite, bounds)) or min_x >= max_x or min_y >= max_y:
            raise ValueError("Projected monitoring bounds are empty or invalid.")
        resolution = float(resolution_meters)
        origin_x = math.floor(min_x / resolution) * resolution
        origin_y = math.ceil(max_y / resolution) * resolution
        width = int(math.ceil((max_x - origin_x) / resolution))
        height = int(math.ceil((origin_y - min_y) / resolution))
        return {
            "transform": [resolution, 0.0, origin_x, 0.0, -resolution, origin_y],
            "width": width,
            "height": height,
            "bounds": [
                origin_x,
                origin_y - height * resolution,
                origin_x + width * resolution,
                origin_y,
            ],
            "resolution_meters": resolution_meters,
        }

    @staticmethod
    def _validate_geotiff_file(output_path: str, expected_grid: Dict[str, Any], crs: str):
        """Validate the native grid and make the exported nodata sentinel explicit."""
        import rasterio
        from affine import Affine

        try:
            with rasterio.open(output_path, "r+") as dataset:
                expected_transform = Affine(*expected_grid["transform"][:6])
                if dataset.count < 3:
                    raise EarthEngineRequestError("Earth Engine GeoTIFF has fewer than three RGB bands.")
                if dataset.crs != rasterio.crs.CRS.from_string(crs):
                    raise EarthEngineRequestError("Earth Engine GeoTIFF CRS differs from the requested common grid.")
                if dataset.transform != expected_transform:
                    raise EarthEngineRequestError("Earth Engine GeoTIFF affine transform differs from the requested common grid.")
                if (dataset.width, dataset.height) != (expected_grid["width"], expected_grid["height"]):
                    raise EarthEngineRequestError("Earth Engine GeoTIFF dimensions differ from the requested common grid.")
                if dataset.nodata != NODATA_VALUE:
                    dataset.nodata = NODATA_VALUE
        except EarthEngineRequestError:
            raise
        except Exception as exc:
            raise EarthEngineRequestError(f"Could not validate downloaded GeoTIFF: {exc}") from exc

    @classmethod
    def _write_geotiff_download(
        cls, content: bytes, output_path: str, expected_grid: Dict[str, Any], crs: str
    ):
        """Unwrap Earth Engine's TIFF response, persist it, and validate the grid."""
        tiff_bytes = content
        if content.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    tiff_names = [
                        item for item in archive.infolist()
                        if item.filename.lower().endswith((".tif", ".tiff"))
                    ]
                    if len(tiff_names) != 1:
                        raise EarthEngineRequestError(
                            f"Expected one multiband GeoTIFF in Earth Engine archive; found {len(tiff_names)}."
                        )
                    tiff_bytes = archive.read(tiff_names[0])
            except zipfile.BadZipFile as exc:
                raise EarthEngineRequestError("Earth Engine returned an invalid GeoTIFF archive.") from exc
        if not (tiff_bytes.startswith(b"II*\x00") or tiff_bytes.startswith(b"MM\x00*")):
            raise EarthEngineRequestError("Earth Engine returned no GeoTIFF data.")

        with open(output_path, "wb") as output:
            output.write(tiff_bytes)
        cls._validate_geotiff_file(output_path, expected_grid, crs)

    @staticmethod
    def _valid_pixel_summary(path: str, geometry: Dict[str, Any]) -> Dict[str, Any]:
        """Count valid acquired pixels inside the complete monitoring polygon."""
        import numpy as np
        import rasterio
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom

        with rasterio.open(path) as dataset:
            projected_geometry = transform_geom(
                "EPSG:4326", dataset.crs, geometry, precision=9
            )
            inside_zone = geometry_mask(
                [projected_geometry],
                out_shape=(dataset.height, dataset.width),
                transform=dataset.transform,
                invert=True,
                all_touched=False,
            )
            valid = (dataset.dataset_mask() > 0) & inside_zone
            zone_pixels = int(np.count_nonzero(inside_zone))
            valid_pixels = int(np.count_nonzero(valid))
            return {
                "valid_pixel_count": valid_pixels,
                "zone_pixel_count": zone_pixels,
                "valid_pixel_coverage_percentage": round(
                    100.0 * valid_pixels / zone_pixels, 2
                ) if zone_pixels else 0.0,
            }

    def _cloud_mask(self, image):
        ee = self._get_ee()
        qa = image.select("QA60")
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        qa_mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
            qa.bitwiseAnd(cirrus_bit_mask).eq(0)
        )
        scl = image.select("SCL")
        scl_mask = (
            scl.neq(3)
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
            .And(scl.neq(11))
        )
        scaled = ee.Image(
            image.select(["B4", "B3", "B2"]).divide(10000)
        ).clip(image.geometry())
        return ee.Image(scaled.updateMask(qa_mask.And(scl_mask)))

    def acquire(
        self,
        geometry: Dict[str, Any],
        start_date: str,
        end_date: str,
        max_cloud_coverage: float = 30.0,
        width: int = 512,
        height: int = 512,
        resolution_meters: int = 10,
    ):
        self.validate_request(
            start_date, end_date, max_cloud_coverage, width, height, resolution_meters
        )
        geometry = self.validate_geometry(geometry)
        self.initialize()
        ee = self._get_ee()

        try:
            ee_geometry = ee.Geometry(geometry)
            collection = (
                ee.ImageCollection(DATASET)
                .filterBounds(ee_geometry)
                .filterDate(
                    start_date,
                    (date.fromisoformat(end_date) + timedelta(days=1)).isoformat(),
                )
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_coverage))
                .sort("CLOUDY_PIXEL_PERCENTAGE")
            )
            if collection.size().getInfo() == 0:
                raise EarthEngineCollectionEmptyError(
                    f"No Sentinel-2 L2A acquisitions found between {start_date} and {end_date} "
                    f"with cloud coverage below {max_cloud_coverage}%."
                )
            selected = collection.first()
            masked = self._cloud_mask(selected)
            masked = masked.clip(ee_geometry)

            properties = selected.toDictionary([
                "system:time_start",
                "CLOUDY_PIXEL_PERCENTAGE",
                "SPACECRAFT_NAME",
                "PLATFORM",
            ]).getInfo()
            timestamp_ms = properties.get("system:time_start")
            acquisition_date = (
                datetime.utcfromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d")
                if timestamp_ms
                else None
            )
            cloud = properties.get("CLOUDY_PIXEL_PERCENTAGE")
            satellite = (
                properties.get("SPACECRAFT_NAME")
                or properties.get("PLATFORM")
                or "Sentinel-2"
            )

            cache_key = hashlib.sha256(
                (
                    repr(geometry)
                    + start_date
                    + end_date
                    + str(max_cloud_coverage)
                    + str(width)
                    + str(height)
                    + str(resolution_meters)
                ).encode("utf-8")
            ).hexdigest()[:16]
            stem = f"gee_{cache_key}_{acquisition_date or 'unknown'}"
            png_path = os.path.join(self.output_dir, stem + ".png")
            zip_path = os.path.join(self.output_dir, stem + ".zip")
            tiff_path = os.path.join(self.output_dir, stem + ".tif")

            target_crs = self.utm_crs_for_geometry(geometry)
            target_projection = ee.Projection(target_crs)
            projected_bounds = ee_geometry.transform(target_projection, 1).bounds(
                1, target_projection
            ).coordinates().getInfo()[0]
            grid_bounds = (
                min(point[0] for point in projected_bounds),
                min(point[1] for point in projected_bounds),
                max(point[0] for point in projected_bounds),
                max(point[1] for point in projected_bounds),
            )
            grid = self.snap_bounds_to_grid(grid_bounds, resolution_meters)
            grid_transform = grid["transform"]
            grid_rectangle = ee.Geometry.Rectangle(
                grid["bounds"], proj=target_projection, geodesic=False
            )
            grid_image = masked.unmask(NODATA_VALUE, False).clip(grid_rectangle)
            cached = all(os.path.isfile(path) for path in (png_path, zip_path, tiff_path))
            if cached:
                try:
                    self._validate_geotiff_file(tiff_path, grid, target_crs)
                except EarthEngineRequestError:
                    cached = False

            if not cached:
                thumb_url = masked.getThumbURL({
                    "dimensions": f"{width}x{height}",
                    "region": ee_geometry,
                    "format": "png",
                    "min": 0,
                    "max": 0.3,
                    "bands": ["B4", "B3", "B2"],
                })
                response = self.session.get(thumb_url, timeout=60)
                response.raise_for_status()
                if not response.content.startswith(b"\x89PNG"):
                    raise EarthEngineRequestError("Earth Engine returned no PNG image data.")
                with open(png_path, "wb") as file:
                    file.write(response.content)

                download_url = grid_image.getDownloadURL({
                    "name": stem,
                    "bands": ["B4", "B3", "B2"],
                    "crs": target_crs,
                    "crs_transform": grid_transform,
                    "format": "GEO_TIFF",
                })
                download = self.session.get(download_url, timeout=120)
                download.raise_for_status()
                with open(zip_path, "wb") as file:
                    file.write(download.content)
                self._write_geotiff_download(download.content, tiff_path, grid, target_crs)

            pixel_summary = self._valid_pixel_summary(tiff_path, geometry)

            png_name = os.path.basename(png_path)
            zip_name = os.path.basename(zip_path)
            return {
                "date": acquisition_date,
                "cloud_coverage_percentage": float(cloud) if cloud is not None else None,
                "satellite": satellite,
                "dataset": DATASET,
                "image_url": f"/storage/earth_engine/{png_name}",
                "thumbnail_url": f"/storage/earth_engine/{png_name}",
                "geotiff_url": f"/storage/earth_engine/{zip_name}",
                "raster_url": f"/storage/earth_engine/{os.path.basename(tiff_path)}",
                "width": width,
                "height": height,
                "raster_width": grid["width"],
                "raster_height": grid["height"],
                "resolution_meters": resolution_meters,
                "crs": target_crs,
                "transform": grid_transform,
                "nodata": NODATA_VALUE,
                **pixel_summary,
                "extent": geometry,
                "available": True,
                "cached": cached,
                "processing_status": "cached" if cached else "completed",
            }
        except (EarthEngineCollectionEmptyError, EarthEngineRequestError):
            raise
        except Exception as exc:
            raise EarthEngineRequestError(
                f"Google Earth Engine request failed: {exc}"
            ) from exc


earth_engine_service = EarthEngineService()
