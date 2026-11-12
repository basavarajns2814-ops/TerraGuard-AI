"""
GIS Change Analysis and Vector Extraction Service.

Transforms neural network binary change masks into georeferenced vector polygons,
computes accurate geodesic metric land area (m² and hectares), intersects changes
with monitored boundaries and restricted corridors, eliminates insignificant noise,
and generates structured GeoJSON evidence.
"""

from typing import Dict, Any, List, Tuple, Optional
import math
import numpy as np
from shapely.geometry import shape, mapping, box, Polygon, MultiPolygon
from shapely.ops import unary_union, transform as shapely_transform

from app.services.spatial import (
    calculate_polygon_area_sqm,
    sqm_to_hectares,
    get_centroid_lat_lng,
    check_intersection_and_buffer,
    find_containing_parcel
)
from app.services.risk_scoring import evaluate_risk_and_confidence
from app.services.change_detection.morphological import extract_connected_components


class GISChangeAnalysisService:
    """Performs rigorous geospatial analysis of change detection outputs."""

    @staticmethod
    def pixel_polygon_to_geographic(
        pixel_geom: Polygon,
        transform_info: Dict[str, Any]
    ) -> Polygon:
        """
        Converts a Shapely polygon from pixel coordinates (col, row)
        to geographic coordinates (lng, lat) in WGS84 EPSG:4326.
        """
        if "affine" in transform_info:
            from affine import Affine
            from rasterio.warp import transform_geom

            affine = Affine(*transform_info["affine"])
            projected = shapely_transform(
                lambda x, y, z=None: affine * (x, y), pixel_geom
            )
            geographic = transform_geom(
                transform_info["crs"],
                "EPSG:4326",
                mapping(projected),
                precision=9,
            )
            return shape(geographic)

        # Compatibility for pre-existing uploaded/demo RGB scenes.
        origin_x = transform_info["origin_x"]
        origin_y = transform_info["origin_y"]
        pixel_size_x = transform_info["pixel_size_x"]
        pixel_size_y = transform_info["pixel_size_y"]
        return shapely_transform(
            lambda x, y, z=None: (origin_x + x * pixel_size_x, origin_y - y * pixel_size_y),
            pixel_geom,
        )

    def extract_change_regions(
        self,
        binary_mask: np.ndarray,
        probability_map: np.ndarray,
        transform_info: Dict[str, Any],
        zone_geojson: Optional[Dict[str, Any]] = None,
        min_area_sqm: float = 40.0,
        min_pixels: int = 15,
        parcels: Optional[List[Any]] = None,
        restricted_boundaries: Optional[List[Any]] = None,
        cloud_coverage_percentage: float = 0.0
    ) -> Dict[str, Any]:
        """
        Extracts georeferenced vector polygons and computes spatial impact statistics.
        """
        h, w = binary_mask.shape[:2]
        components = extract_connected_components(binary_mask, min_pixels=min_pixels)

        zone_shape = None
        projected_zone = None
        native_crs = transform_info.get("crs") if "affine" in transform_info else None
        if zone_geojson:
            try:
                zone_shape = shape(zone_geojson)
                if not zone_shape.is_valid:
                    zone_shape = zone_shape.buffer(0)
                if native_crs and native_crs != "EPSG:4326":
                    from rasterio.warp import transform_geom

                    projected_zone = shape(
                        transform_geom(
                            "EPSG:4326", native_crs, zone_geojson, precision=9
                        )
                    )
                else:
                    projected_zone = zone_shape
            except Exception as exc:
                if native_crs:
                    raise ValueError(
                        "Unable to project the monitoring zone into the raster CRS."
                    ) from exc
                zone_shape = None
                projected_zone = None

        detected_regions = []
        total_changed_sqm = 0.0

        for comp in components:
            blob_points = comp.get("points", [])
            if not blob_points:
                continue

            # Build exact vector polygon from unit pixel squares
            pixel_boxes = [box(px, py, px + 1, py + 1) for px, py in blob_points]
            pixel_polygon = unary_union(pixel_boxes)

            # Simplify staircase raster edges slightly
            if pixel_polygon.geom_type == "Polygon":
                pixel_polygon = pixel_polygon.simplify(0.35, preserve_topology=True)
            elif pixel_polygon.geom_type == "MultiPolygon":
                pixel_polygon = pixel_polygon.simplify(0.35, preserve_topology=True)

            if "affine" in transform_info:
                from affine import Affine

                affine = Affine(*transform_info["affine"])
                projected_polygon = shapely_transform(
                    lambda x, y, z=None: affine * (x, y), pixel_polygon
                )
            else:
                projected_polygon = None
                geo_polygon = self.pixel_polygon_to_geographic(pixel_polygon, transform_info)

            # Clip in the source projected CRS before computing metric area.
            if projected_polygon is not None and projected_zone is not None:
                if not projected_polygon.intersects(projected_zone):
                    continue
                projected_polygon = projected_polygon.intersection(projected_zone)

            if projected_polygon is not None:
                if projected_polygon.is_empty:
                    continue
                geo_polygon = self.pixel_polygon_to_geographic(
                    pixel_polygon, transform_info
                )
                if projected_zone is not None:
                    # Convert the clipped shape rather than its original pixel outline.
                    from rasterio.warp import transform_geom

                    geo_polygon = shape(transform_geom(
                        native_crs, "EPSG:4326", mapping(projected_polygon), precision=9
                    ))
                area_sqm = float(projected_polygon.area)
            else:
                if zone_shape is not None and not zone_shape.is_empty:
                    try:
                        if geo_polygon.intersects(zone_shape):
                            geo_polygon = geo_polygon.intersection(zone_shape)
                        else:
                            continue
                    except Exception:
                        pass
                area_sqm = calculate_polygon_area_sqm(mapping(geo_polygon))

            if geo_polygon.is_empty:
                continue

            # Compute metric area in square meters
            geo_dict = mapping(geo_polygon)
            # Filter noise below minimum threshold
            if area_sqm < min_area_sqm:
                continue

            area_ha = sqm_to_hectares(area_sqm)
            total_changed_sqm += area_sqm

            centroid_lat, centroid_lng = get_centroid_lat_lng(geo_dict)

            # Mean model confidence probability within this cluster
            xs = [p[0] for p in blob_points if 0 <= p[0] < w and 0 <= p[1] < h]
            ys = [p[1] for p in blob_points if 0 <= p[0] < w and 0 <= p[1] < h]
            if xs and ys and probability_map is not None:
                cluster_probs = [float(probability_map[y, x]) for x, y in zip(xs, ys)]
                mean_prob = float(np.mean(cluster_probs))
                max_prob = float(np.max(cluster_probs))
            else:
                mean_prob = 0.85
                max_prob = 0.90

            # Match containing parcel
            matched_parcel = find_containing_parcel(geo_dict, parcels or [])
            parcel_id = matched_parcel.id if matched_parcel else None
            parcel_number = matched_parcel.parcel_number if matched_parcel else None
            owner_type = matched_parcel.owner_type if matched_parcel else "UNKNOWN"

            # Check intersection and proximity with statutory buffer corridors
            intersects_restricted = False
            restricted_name = None
            proximity_m = 9999.0

            for rb in (restricted_boundaries or []):
                if rb.geojson:
                    res = check_intersection_and_buffer(geo_dict, rb.geojson, rb.buffer_distance_meters)
                    if res["intersects"]:
                        intersects_restricted = True
                        restricted_name = rb.name
                        proximity_m = 0.0
                        break
                    elif res["in_buffer"] and res["distance_meters"] < proximity_m:
                        proximity_m = res["distance_meters"]
                        restricted_name = rb.name

            # Land cover change classification
            if intersects_restricted and "Lake" in (restricted_name or ""):
                category = "WATER_BODY_ENCROACHMENT"
            elif area_sqm > 1200.0:
                category = "NEW_CONSTRUCTION"
            elif area_sqm > 400.0:
                category = "EXPANSION"
            else:
                category = "VEGETATION_LOSS"

            # Rule-based explainable risk assessment
            risk_score, risk_level, confidence, reasons = evaluate_risk_and_confidence(
                category=category,
                affected_area_sqm=area_sqm,
                intersects_restricted=intersects_restricted,
                restricted_zone_name=restricted_name,
                proximity_meters=proximity_m,
                observation_count=1,
                trend="NEW",
                cloud_coverage_percentage=cloud_coverage_percentage,
                parcel_owner_type=owner_type
            )

            # Blend with neural network probability
            final_confidence = round(0.5 * confidence + 0.5 * mean_prob, 3)

            detected_regions.append({
                "geojson": geo_dict,
                "area_sqm": round(area_sqm, 2),
                "area_hectares": area_ha,
                "centroid_lat": centroid_lat,
                "centroid_lng": centroid_lng,
                "category": category,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "confidence_score": final_confidence,
                "mean_probability": round(mean_prob, 3),
                "max_probability": round(max_prob, 3),
                "intersects_restricted": intersects_restricted,
                "restricted_zone_name": restricted_name,
                "parcel_id": parcel_id,
                "parcel_number": parcel_number,
                "risk_reasons": reasons
            })

        # Calculate monitored area
        monitored_area_ha = 0.0
        if projected_zone is not None and not projected_zone.is_empty and native_crs:
            monitored_area_sqm = float(projected_zone.area)
            monitored_area_ha = sqm_to_hectares(monitored_area_sqm)
        elif zone_shape is not None and not zone_shape.is_empty:
            monitored_area_sqm = calculate_polygon_area_sqm(zone_geojson)
            monitored_area_ha = sqm_to_hectares(monitored_area_sqm)

        total_changed_ha = sqm_to_hectares(total_changed_sqm)
        change_percentage = (
            round((total_changed_sqm / (monitored_area_ha * 10000.0)) * 100.0, 3)
            if monitored_area_ha > 0
            else 0.0
        )

        return {
            "monitored_area_hectares": monitored_area_ha,
            "total_changed_area_sqm": round(total_changed_sqm, 2),
            "total_changed_area_hectares": total_changed_ha,
            "change_percentage_of_monitored_area": change_percentage,
            "region_count": len(detected_regions),
            "regions": detected_regions
        }


gis_change_analysis_service = GISChangeAnalysisService()
