import numpy as np
from typing import List, Dict, Any, Tuple
from PIL import Image, ImageFilter

def morphological_clean(binary_mask: np.ndarray, min_area_pixels: int = 25) -> np.ndarray:
    """
    Cleans binary mask using morphological operations (dilation/erosion)
    to remove speckle noise and merge adjacent change fragments.
    Uses pure PIL/NumPy without requiring binary C++ bindings.
    """
    img = Image.fromarray(binary_mask)
    # Median filter removes salt-and-pepper noise
    cleaned = img.filter(ImageFilter.MedianFilter(size=3))
    # Max filter (dilation)
    dilated = cleaned.filter(ImageFilter.MaxFilter(size=3))
    # Min filter (erosion)
    eroded = dilated.filter(ImageFilter.MinFilter(size=3))

    return np.array(eroded)

def extract_connected_components(
    binary_mask: np.ndarray,
    min_pixels: int = 30
) -> List[Dict[str, Any]]:
    """
    Identifies connected candidate blobs in the binary mask
    and extracts bounding boxes and approximate boundary contours.
    """
    h, w = binary_mask.shape
    visited = np.zeros((h, w), dtype=bool)
    components = []

    # Simple 8-connected flood fill or grid-stride component search
    stride = 2
    for y in range(0, h, stride):
        for x in range(0, w, stride):
            if binary_mask[y, x] > 128 and not visited[y, x]:
                # Collect connected points
                stack = [(y, x)]
                visited[y, x] = True
                blob_points = []

                while stack:
                    cy, cx = stack.pop()
                    blob_points.append((cx, cy))

                    # 4-neighbors
                    for ny, nx in [(cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)]:
                        if 0 <= ny < h and 0 <= nx < w:
                            if not visited[ny, nx] and binary_mask[ny, nx] > 128:
                                visited[ny, nx] = True
                                stack.append((ny, nx))

                if len(blob_points) >= min_pixels:
                    xs = [p[0] for p in blob_points]
                    ys = [p[1] for p in blob_points]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)

                    components.append({
                        "pixel_count": len(blob_points),
                        "bbox": (min_x, min_y, max_x, max_y),
                        "points": blob_points
                    })

    return components

def pixel_to_geo_coords(
    x: float,
    y: float,
    img_width: int,
    img_height: int,
    bbox_geo: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """
    Maps pixel (x, y) to (latitude, longitude).
    bbox_geo format: (min_lng, min_lat, max_lng, max_lat)
    """
    min_lng, min_lat, max_lng, max_lat = bbox_geo
    lng = min_lng + (x / float(img_width)) * (max_lng - min_lng)
    lat = max_lat - (y / float(img_height)) * (max_lat - min_lat)
    return (round(lat, 6), round(lng, 6))

def component_to_geojson_polygon(
    component: Dict[str, Any],
    img_width: int,
    img_height: int,
    bbox_geo: Tuple[float, float, float, float]
) -> Dict[str, Any]:
    """
    Constructs a GeoJSON polygon from component bounding box / convex outline.
    """
    min_x, min_y, max_x, max_y = component["bbox"]

    # 5-point bounding polygon in [lng, lat] GeoJSON standard order
    p1_lat, p1_lng = pixel_to_geo_coords(min_x, min_y, img_width, img_height, bbox_geo)
    p2_lat, p2_lng = pixel_to_geo_coords(max_x, min_y, img_width, img_height, bbox_geo)
    p3_lat, p3_lng = pixel_to_geo_coords(max_x, max_y, img_width, img_height, bbox_geo)
    p4_lat, p4_lng = pixel_to_geo_coords(min_x, max_y, img_width, img_height, bbox_geo)

    coordinates = [[
        [p1_lng, p1_lat],
        [p2_lng, p2_lat],
        [p3_lng, p3_lat],
        [p4_lng, p4_lat],
        [p1_lng, p1_lat] # Close ring
    ]]

    return {
        "type": "Polygon",
        "coordinates": coordinates
    }
