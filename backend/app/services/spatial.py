import math
import re
from typing import Dict, Any, Tuple, List, Optional
from shapely.geometry import shape, mapping, Polygon, Point, MultiPolygon
from shapely.ops import transform
from rasterio.warp import transform_geom

# Standard WGS84 ellipsoid geodetic transformer for area computation in square meters
def calculate_polygon_area_sqm(geom_geojson: Dict[str, Any]) -> float:
    """
    Calculates geodesic area in square meters for a GeoJSON polygon
    using equal-area or cylindrical projection projection centered on centroid.
    """
    try:
        geom = shape(geom_geojson)
        if geom.is_empty:
            return 0.0

        # Approximate latitude/longitude to metric conversion around India/Karnataka (Lat ~12-15N)
        centroid = geom.centroid
        lat_rad = math.radians(centroid.y)
        # 1 deg latitude ~ 111,000 meters
        # 1 deg longitude ~ 111,000 * cos(lat) meters
        m_per_deg_lat = 111320.0
        m_per_deg_lng = 111320.0 * math.cos(lat_rad)

        # Scale polygon to metric coords
        def to_meters(x, y, z=None):
            return (x * m_per_deg_lng, y * m_per_deg_lat)

        metric_geom = transform(to_meters, geom)
        return float(metric_geom.area)
    except Exception as e:
        print(f"Area computation error: {e}")
        return 0.0

def sqm_to_hectares(sqm: float) -> float:
    return round(sqm / 10000.0, 4)

def get_centroid_lat_lng(geom_geojson: Dict[str, Any]) -> Tuple[float, float]:
    """Returns (latitude, longitude) of geometry centroid"""
    try:
        geom = shape(geom_geojson)
        centroid = geom.centroid
        return (float(centroid.y), float(centroid.x))
    except Exception:
        return (12.9352, 77.6245) # Default Bengaluru coordinates


def _empty_metric_result() -> Dict[str, Any]:
    return {
        "intersects": False,
        "in_buffer": False,
        "distance_meters": 9999.0,
        "violation_type": "UNKNOWN"
    }


def _crs_is_wgs84(crs_value: Any) -> bool:
    if crs_value is None:
        return True
    if isinstance(crs_value, str):
        normalized = re.sub(r"[\s_-]", "", crs_value.upper())
        return normalized in {
            "EPSG:4326",
            "EPSG4326",
            "EPSG:1:4326",
            "OGC:CRS84",
            "OGCCRS84",
            "URN:OGC:DEF:CRS:EPSG::4326",
            "URN:OGC:DEF:CRS:OGC:1.3:CRS84",
            "WGS84",
            "4326",
        }
    return False


def _parse_explicit_crs(value: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if "crs" not in value:
        return True, "EPSG:4326"

    crs_value = value.get("crs")
    if isinstance(crs_value, str):
        candidate = crs_value
    elif isinstance(crs_value, dict):
        properties = crs_value.get("properties")
        if isinstance(properties, dict):
            candidate = (
                properties.get("name")
                or properties.get("code")
                or properties.get("href")
            )
            if properties.get("code") is not None and candidate == properties.get("code"):
                if isinstance(candidate, (int, float)):
                    candidate = f"EPSG:{int(candidate)}"
                elif isinstance(candidate, str) and candidate.strip().isdigit():
                    candidate = f"EPSG:{candidate.strip()}"
        else:
            candidate = crs_value.get("name") or crs_value.get("code") or crs_value.get("href")

        if isinstance(candidate, int):
            candidate = f"EPSG:{candidate}"
    else:
        return False, None

    if not isinstance(candidate, str) or not candidate.strip():
        return False, None
    if _crs_is_wgs84(candidate):
        return True, "EPSG:4326"
    return False, candidate


def _has_finite_coordinates(coordinates: Any) -> bool:
    if isinstance(coordinates, (list, tuple)):
        return all(_has_finite_coordinates(item) for item in coordinates)
    return isinstance(coordinates, (int, float)) and math.isfinite(float(coordinates))


def _crosses_antimeridian_ring(coordinates: Any) -> bool:
    if isinstance(coordinates, list) and coordinates and isinstance(coordinates[0], list):
        if coordinates and isinstance(coordinates[0][0], list):
            return any(_crosses_antimeridian_ring(part) for part in coordinates)
        for index in range(len(coordinates) - 1):
            current = coordinates[index]
            following = coordinates[index + 1]
            if isinstance(current, (list, tuple)) and isinstance(following, (list, tuple)):
                if len(current) >= 2 and len(following) >= 2:
                    if abs(float(current[0]) - float(following[0])) > 180.0:
                        return True
    return False


def _geometry_from_service_input(value: Any, default_crs: str = "EPSG:4326"):
    if value is None:
        return None, None

    if hasattr(value, "geom_type"):
        geom = value
        if geom.geom_type not in {
            "Point", "MultiPoint", "LineString", "MultiLineString",
            "Polygon", "MultiPolygon",
        }:
            return None, default_crs
        if geom.is_empty or not geom.is_valid:
            return None, default_crs
        return geom, default_crs

    if not isinstance(value, dict):
        return None, None

    valid_crs, parsed_crs = _parse_explicit_crs(value)
    if not valid_crs:
        return None, parsed_crs

    try:
        geom = shape(value)
    except Exception:
        return None, default_crs

    if geom.is_empty or geom.geom_type not in {
        "Point", "MultiPoint", "LineString", "MultiLineString",
        "Polygon", "MultiPolygon",
    }:
        return None, default_crs

    if not geom.is_valid:
        return None, default_crs

    coordinates = value.get("coordinates")
    if coordinates is not None:
        if not _has_finite_coordinates(coordinates):
            return None, default_crs
        if _crosses_antimeridian_ring(coordinates):
            return None, default_crs

    return geom, "EPSG:4326"


def _combined_metric_crs(change_geom: Polygon, boundary_geom: Polygon) -> str:
    combined = change_geom.union(boundary_geom)
    centroid = combined.centroid
    bounds = combined.bounds

    if not (
        math.isfinite(centroid.x)
        and math.isfinite(centroid.y)
        and all(math.isfinite(bound) for bound in bounds)
    ):
        raise ValueError("Geometry coordinates must be finite.")

    longitude_min = bounds[0]
    longitude_max = bounds[2]
    longitude_mid = (longitude_min + longitude_max) / 2.0
    latitude = centroid.y

    western_zone = math.floor((longitude_min + 180.0) / 6.0) + 1
    eastern_zone = math.floor((longitude_max + 180.0) / 6.0) + 1
    midpoint_zone = math.floor((longitude_mid + 180.0) / 6.0) + 1

    zone_crossing = western_zone != eastern_zone
    antimeridian_crossing = longitude_max - longitude_min > 180.0

    if zone_crossing or antimeridian_crossing or not (-80.0 <= latitude <= 84.0):
        return (
            f"+proj=aeqd +lat_0={latitude:.10f} +lon_0={centroid.x:.10f} "
            "+datum=WGS84 +units=m +no_defs"
        )

    zone = max(1, min(60, int(midpoint_zone)))
    epsg = (32600 + zone) if latitude >= 0.0 else (32700 + zone)
    return f"EPSG:{epsg}"


def _project_wgs84_geometry(geom, metric_crs: str):
    projected = transform_geom(
        "EPSG:4326",
        metric_crs,
        mapping(geom),
        precision=9,
    )
    return shape(projected)


def check_intersection_and_buffer(
    change_geom_geojson: Dict[str, Any],
    boundary_geom_geojson: Dict[str, Any],
    buffer_meters: float = 30.0
) -> Dict[str, Any]:
    """
    Checks spatial intersection and proximity warning between candidate change and a protected boundary.
    Distinguishes direct intersection from proximity warning.

    Service inputs are conventionally WGS84 GeoJSON longitude/latitude. Metric
    calculations are performed after projecting a copy of both geometries into
    a local UTM CRS, or a local azimuthal-equidistant CRS for cross-UTM cases.
    Raw Shapely geometries without CRS metadata are assumed to be WGS84.
    The original stored GeoJSON is never mutated.
    """
    try:
        if buffer_meters is None or not math.isfinite(float(buffer_meters)):
            return _empty_metric_result()
        buffer_meters = float(buffer_meters)
        if buffer_meters < 0.0:
            return _empty_metric_result()

        change_geom, change_crs = _geometry_from_service_input(change_geom_geojson)
        boundary_geom, boundary_crs = _geometry_from_service_input(boundary_geom_geojson)
        if change_geom is None or boundary_geom is None:
            return _empty_metric_result()
        if change_crs != "EPSG:4326" or boundary_crs != "EPSG:4326":
            return _empty_metric_result()

        intersects = change_geom.intersects(boundary_geom)
        metric_crs = _combined_metric_crs(change_geom, boundary_geom)
        projected_change = _project_wgs84_geometry(change_geom, metric_crs)
        projected_boundary = _project_wgs84_geometry(boundary_geom, metric_crs)

        if projected_change.is_empty or projected_boundary.is_empty:
            return _empty_metric_result()

        distance_meters = projected_change.distance(projected_boundary)
        buffered_boundary = projected_boundary.buffer(buffer_meters)
        in_buffer = bool(projected_change.intersects(buffered_boundary))

        return {
            "intersects": bool(intersects),
            "in_buffer": bool(in_buffer),
            "distance_meters": round(float(distance_meters), 2),
            "violation_type": "DIRECT_INTERSECTION" if intersects else ("PROXIMITY_WARNING" if in_buffer else "CLEAR")
        }
    except Exception:
        return _empty_metric_result()

def find_containing_parcel(
    change_geom_geojson: Dict[str, Any],
    parcels: List[Any]
) -> Optional[Any]:
    """Finds which land parcel contains or has highest overlap with the candidate change"""
    try:
        change_geom = shape(change_geom_geojson)
        if change_geom.is_empty or not change_geom.is_valid:
            return None
        if change_geom.geom_type not in {"Polygon", "MultiPolygon"}:
            return None
        if not all(math.isfinite(value) for value in change_geom.bounds):
            return None

        best_parcel = None
        max_overlap_area = 0.0

        for parcel in parcels:
            if not parcel.geojson:
                continue
            try:
                parcel_geom = shape(parcel.geojson)
            except Exception:
                continue
            if parcel_geom.is_empty or not parcel_geom.is_valid:
                continue
            if parcel_geom.geom_type not in {"Polygon", "MultiPolygon"}:
                continue
            if not all(math.isfinite(value) for value in parcel_geom.bounds):
                continue
            if change_geom.intersects(parcel_geom):
                overlap = change_geom.intersection(parcel_geom).area
                if overlap > max_overlap_area:
                    max_overlap_area = overlap
                    best_parcel = parcel

        return best_parcel
    except Exception:
        return None
