"""
Geospatial Preprocessing and Alignment Service for Sentinel-2 Imagery.

Matches coordinate reference systems, geographical extents, aligns raster grids,
preserves geospatial transforms, applies cloud/nodata masks, and prepares aligned
raster pairs for SNUNet-CD change detection without unreferenced spatial deformation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List, Union
import numpy as np
from PIL import Image
from shapely.geometry import shape


@dataclass
class GeoTIFFScene:
    """RGB raster pixels and source georeferencing read from a GeoTIFF."""

    pixels: np.ndarray
    valid_mask: np.ndarray
    crs: Any
    transform: Any
    width: int
    height: int
    resolution: Tuple[float, float]
    nodata: Optional[float]


def read_geotiff_scene(path: Union[str, Path]) -> GeoTIFFScene:
    """Read three RGB bands and preserve georeferencing and nodata validity."""
    try:
        import rasterio
    except ImportError as exc:
        raise GeospatialAlignmentError(
            "Rasterio is required to read native GeoTIFF imagery."
        ) from exc

    try:
        with rasterio.open(path) as dataset:
            if dataset.count < 3:
                raise GeospatialAlignmentError(
                    f"Expected at least three RGB bands; GeoTIFF has {dataset.count}."
                )
            if dataset.crs is None:
                raise GeospatialAlignmentError("GeoTIFF has no CRS metadata.")
            if dataset.width <= 0 or dataset.height <= 0:
                raise GeospatialAlignmentError("GeoTIFF dimensions must be positive.")

            bands = dataset.read((1, 2, 3))
            band_masks = dataset.read_masks((1, 2, 3))
            valid_mask = np.all(band_masks > 0, axis=0)
            valid_mask &= np.all(np.isfinite(bands), axis=0)
            pixels = np.moveaxis(bands, 0, -1)
            resolution = (
                float(np.hypot(dataset.transform.a, dataset.transform.d)),
                float(np.hypot(dataset.transform.b, dataset.transform.e)),
            )
            return GeoTIFFScene(
                pixels=pixels,
                valid_mask=valid_mask,
                crs=dataset.crs,
                transform=dataset.transform,
                width=dataset.width,
                height=dataset.height,
                resolution=resolution,
                nodata=dataset.nodata,
            )
    except GeospatialAlignmentError:
        raise
    except Exception as exc:
        raise GeospatialAlignmentError(f"Could not read GeoTIFF {path}: {exc}") from exc


def require_matching_raster_grids(historical: GeoTIFFScene, recent: GeoTIFFScene) -> None:
    """Reject a pair unless CRS, affine transform, and dimensions are identical."""
    if historical.crs != recent.crs:
        raise GeospatialAlignmentError("Historical and recent GeoTIFF CRS values differ.")
    if historical.transform != recent.transform:
        raise GeospatialAlignmentError(
            "Historical and recent GeoTIFF affine transforms differ."
        )
    if (historical.width, historical.height) != (recent.width, recent.height):
        raise GeospatialAlignmentError(
            "Historical and recent GeoTIFF dimensions differ."
        )


def align_geotiff_pair(
    historical_path: Union[str, Path], recent_path: Union[str, Path]
) -> Dict[str, Any]:
    """Read a native pair and warp the recent raster onto the historical grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    historical = read_geotiff_scene(historical_path)
    recent = read_geotiff_scene(recent_path)
    target_transform = historical.transform
    target_crs = historical.crs
    target_shape = (historical.height, historical.width)

    if (recent.crs, recent.transform, recent.width, recent.height) == (
        target_crs,
        target_transform,
        historical.width,
        historical.height,
    ):
        recent_pixels = recent.pixels.astype(np.float32, copy=False)
        recent_valid = recent.valid_mask.copy()
    else:
        recent_pixels = np.zeros((historical.height, historical.width, 3), dtype=np.float32)
        dst_nodata = historical.nodata if historical.nodata is not None else -9999.0
        recent_pixels.fill(dst_nodata)
        src_nodata = recent.nodata if recent.nodata is not None else -9999.0
        for band_index in range(3):
            source_band = recent.pixels[:, :, band_index].astype(np.float32, copy=True)
            source_band[~recent.valid_mask] = src_nodata
            reproject(
                source=source_band,
                destination=recent_pixels[:, :, band_index],
                src_transform=recent.transform,
                src_crs=recent.crs,
                src_nodata=src_nodata,
                dst_transform=target_transform,
                dst_crs=target_crs,
                dst_nodata=dst_nodata,
                resampling=Resampling.bilinear,
            )
        warped_valid = np.zeros(target_shape, dtype=np.uint8)
        reproject(
            source=recent.valid_mask.astype(np.uint8),
            destination=warped_valid,
            src_transform=recent.transform,
            src_crs=recent.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            src_nodata=0,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )
        recent_valid = warped_valid > 0

    hist_pixels = historical.pixels.astype(np.float32, copy=False)
    valid_mask = historical.valid_mask & recent_valid
    valid_mask &= np.all(np.isfinite(hist_pixels), axis=2)
    valid_mask &= np.all(np.isfinite(recent_pixels), axis=2)
    if historical.nodata is not None:
        valid_mask &= np.all(hist_pixels != historical.nodata, axis=2)
    if recent.nodata is not None:
        valid_mask &= np.all(recent_pixels != recent.nodata, axis=2)

    # Earth Engine exports scaled Sentinel-2 reflectance in [0, 1]. Apply the
    # same 0–0.3 display stretch as the retained PNG preview, while deriving
    # every model pixel from the native TIFF samples.
    stretch = 255.0 / 0.3
    hist_rgb = np.clip(hist_pixels * stretch, 0, 255).astype(np.uint8)
    recent_rgb = np.clip(recent_pixels * stretch, 0, 255).astype(np.uint8)
    hist_rgb[~valid_mask] = 0
    recent_rgb[~valid_mask] = 0

    affine = target_transform
    transform_info = {
        "crs": target_crs.to_string(),
        "affine": [affine.a, affine.b, affine.c, affine.d, affine.e, affine.f],
        "width": historical.width,
        "height": historical.height,
        "resolution": historical.resolution,
    }
    return {
        "historical_aligned": hist_rgb,
        "recent_aligned": recent_rgb,
        "historical_reflectance": hist_pixels,
        "recent_reflectance": recent_pixels,
        "valid_mask": valid_mask,
        "transform": transform_info,
        "crs": target_crs.to_string(),
        "dimensions": {"width": historical.width, "height": historical.height, "channels": 3},
        "resampled_recent": not (
            recent.crs == target_crs
            and recent.transform == target_transform
            and recent.width == historical.width
            and recent.height == historical.height
        ),
    }


class GeospatialAlignmentError(ValueError):
    """Raised when satellite scenes cannot be spatially aligned."""
    pass


class GeospatialPreprocessor:
    """Preprocesses and aligns multi-temporal satellite scene pairs."""

    @staticmethod
    def extract_bounding_box(geometry: Dict[str, Any]) -> Tuple[float, float, float, float]:
        """
        Extracts (min_lng, min_lat, max_lng, max_lat) in WGS84 EPSG:4326 from GeoJSON.
        """
        if not geometry:
            raise GeospatialAlignmentError("Monitoring geometry cannot be empty.")
        try:
            geom = shape(geometry)
            min_lng, min_lat, max_lng, max_lat = geom.bounds
            return float(min_lng), float(min_lat), float(max_lng), float(max_lat)
        except Exception as exc:
            raise GeospatialAlignmentError(f"Failed to extract geospatial bounds: {exc}") from exc

    @staticmethod
    def calculate_geospatial_transform(
        bbox: Tuple[float, float, float, float],
        width: int,
        height: int,
        crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        """
        Calculates affine geographic pixel transform:
        pixel (col, row) -> geographic (lng, lat)
        """
        min_lng, min_lat, max_lng, max_lat = bbox
        if width <= 0 or height <= 0:
            raise GeospatialAlignmentError("Raster dimensions must be positive integers.")

        pixel_size_x = (max_lng - min_lng) / float(width)
        pixel_size_y = (max_lat - min_lat) / float(height)

        return {
            "crs": crs,
            "bbox": bbox,
            "width": width,
            "height": height,
            "pixel_size_x": pixel_size_x,
            "pixel_size_y": pixel_size_y,
            "origin_x": min_lng,
            "origin_y": max_lat,
            "units": "degrees"
        }

    @staticmethod
    def pixel_to_geographic(
        col: float,
        row: float,
        transform: Dict[str, Any]
    ) -> Tuple[float, float]:
        """
        Transforms raster pixel coordinate (col, row) to geographic (lng, lat).
        """
        lng = transform["origin_x"] + (col * transform["pixel_size_x"])
        lat = transform["origin_y"] - (row * transform["pixel_size_y"])
        return round(float(lng), 7), round(float(lat), 7)

    @staticmethod
    def geographic_to_pixel(
        lng: float,
        lat: float,
        transform: Dict[str, Any]
    ) -> Tuple[int, int]:
        """
        Transforms geographic (lng, lat) to raster pixel coordinate (col, row).
        """
        col = int(round((lng - transform["origin_x"]) / transform["pixel_size_x"]))
        row = int(round((transform["origin_y"] - lat) / transform["pixel_size_y"]))
        return col, row

    def align_and_preprocess_pair(
        self,
        historical_img: np.ndarray,
        recent_img: np.ndarray,
        geometry: Optional[Dict[str, Any]] = None,
        target_dimensions: Tuple[int, int] = (512, 512),
        fallback_bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> Dict[str, Any]:
        """
        Aligns historical and recent satellite scenes to a common georeferenced raster grid:
        - Validates 3-channel RGB structure
        - Computes affine geospatial transform for the monitored extent
        - Harmonizes dimensions using high-fidelity bilinear resampling if dimensions vary
        - Identifies invalid/masked pixels (black borders, cloud mask voids)
        """
        if historical_img.ndim != 3 or historical_img.shape[2] != 3:
            raise GeospatialAlignmentError("Historical scene must be a 3-channel RGB raster.")
        if recent_img.ndim != 3 or recent_img.shape[2] != 3:
            raise GeospatialAlignmentError("Recent scene must be a 3-channel RGB raster.")

        # Determine bounding box
        if geometry:
            bbox = self.extract_bounding_box(geometry)
        elif fallback_bbox:
            bbox = fallback_bbox
        else:
            # Default Karnataka/Bengaluru demonstration extent
            bbox = (77.6550, 12.9250, 77.6950, 12.9550)

        target_w, target_h = target_dimensions

        # Harmonize dimensions if needed, preserving geographic alignment
        h_h, h_w = historical_img.shape[:2]
        r_h, r_w = recent_img.shape[:2]

        if (h_w, h_h) != (target_w, target_h):
            h_pil = Image.fromarray(historical_img).resize((target_w, target_h), Image.Resampling.BILINEAR)
            hist_aligned = np.asarray(h_pil, dtype=np.uint8)
        else:
            hist_aligned = historical_img.copy()

        if (r_w, r_h) != (target_w, target_h):
            r_pil = Image.fromarray(recent_img).resize((target_w, target_h), Image.Resampling.BILINEAR)
            recent_aligned = np.asarray(r_pil, dtype=np.uint8)
        else:
            recent_aligned = recent_img.copy()

        transform = self.calculate_geospatial_transform(bbox, target_w, target_h)

        # Detect nodata/void pixels (e.g. from cloud masking or out-of-swath bounds)
        hist_valid = np.any(hist_aligned > 5, axis=-1)
        recent_valid = np.any(recent_aligned > 5, axis=-1)
        valid_mask = hist_valid & recent_valid

        # Scale reflectance consistently to [0.0, 1.0] float32
        hist_norm = hist_aligned.astype(np.float32) / 255.0
        recent_norm = recent_aligned.astype(np.float32) / 255.0

        return {
            "historical_aligned": hist_aligned,
            "recent_aligned": recent_aligned,
            "historical_norm": hist_norm,
            "recent_norm": recent_norm,
            "valid_mask": valid_mask,
            "transform": transform,
            "bbox": bbox,
            "dimensions": {"width": target_w, "height": target_h, "channels": 3},
            "crs": "EPSG:4326"
        }


geospatial_preprocessor = GeospatialPreprocessor()
