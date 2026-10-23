import math
from typing import Dict, Any, Tuple, List, Optional
from shapely.geometry import shape, mapping, Polygon, Point, MultiPolygon
from shapely.ops import transform

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

def check_intersection_and_buffer(
    change_geom_geojson: Dict[str, Any],
    boundary_geom_geojson: Dict[str, Any],
    buffer_meters: float = 30.0
) -> Dict[str, Any]:
    """
    Checks spatial intersection and proximity warning between candidate change and a protected boundary.
    Distinguishes direct intersection from proximity warning.
    """
    try:
        change_geom = shape(change_geom_geojson)
        boundary_geom = shape(boundary_geom_geojson)

        # Check direct intersection
        intersects = change_geom.intersects(boundary_geom)

        # Check proximity buffer
        # Convert ~meters to degrees approximately (30m ~ 0.00027 degrees)
        deg_buffer = buffer_meters / 111320.0
        buffered_boundary = boundary_geom.buffer(deg_buffer)
        in_buffer = change_geom.intersects(buffered_boundary)

        # Compute minimum distance in meters
        distance_deg = change_geom.distance(boundary_geom)
        distance_meters = distance_deg * 111320.0

        return {
            "intersects": bool(intersects),
            "in_buffer": bool(in_buffer),
            "distance_meters": round(float(distance_meters), 2),
            "violation_type": "DIRECT_INTERSECTION" if intersects else ("PROXIMITY_WARNING" if in_buffer else "CLEAR")
        }
    except Exception as e:
        print(f"Spatial check error: {e}")
        return {
            "intersects": False,
            "in_buffer": False,
            "distance_meters": 9999.0,
            "violation_type": "UNKNOWN"
        }

def find_containing_parcel(
    change_geom_geojson: Dict[str, Any],
    parcels: List[Any]
) -> Optional[Any]:
    """Finds which land parcel contains or has highest overlap with the candidate change"""
    try:
        change_geom = shape(change_geom_geojson)
        best_parcel = None
        max_overlap_area = 0.0

        for parcel in parcels:
            if not parcel.geojson:
                continue
            parcel_geom = shape(parcel.geojson)
            if change_geom.intersects(parcel_geom):
                overlap = change_geom.intersection(parcel_geom).area
                if overlap > max_overlap_area:
                    max_overlap_area = overlap
                    best_parcel = parcel

        return best_parcel
    except Exception:
        return None
