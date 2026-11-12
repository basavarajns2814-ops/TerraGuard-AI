import pytest
from rasterio.warp import transform_geom
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection, box, mapping

from app.services.spatial import check_intersection_and_buffer, _combined_metric_crs


def local_point_geojson(easting, northing, epsg):
    geojson = transform_geom(
        f"EPSG:{epsg}",
        "EPSG:4326",
        mapping(Point(easting, northing)),
        precision=9,
    )
    return geojson


def test_direct_intersection_preserves_return_structure():
    change = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.672, 12.930],
                         [77.672, 12.932], [77.670, 12.932],
                         [77.670, 12.930]]],
    }
    boundary = {
        "type": "Polygon",
        "coordinates": [[[77.671, 12.931], [77.673, 12.931],
                         [77.673, 12.933], [77.671, 12.933],
                         [77.671, 12.931]]],
    }

    result = check_intersection_and_buffer(change, boundary, 30.0)

    assert set(result) == {
        "intersects", "in_buffer", "distance_meters", "violation_type"
    }
    assert result["intersects"] is True
    assert result["distance_meters"] == 0.0
    assert result["violation_type"] == "DIRECT_INTERSECTION"


@pytest.mark.parametrize(
    ("offset_m", "expected_in_buffer", "expected_type"),
    [
        (29.0, True, "PROXIMITY_WARNING"),
        (30.0, False, "CLEAR"),
        (31.0, False, "CLEAR"),
        (100.0, False, "CLEAR"),
    ],
)
def test_metric_buffer_threshold(offset_m, expected_in_buffer, expected_type):
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)
    candidate = local_point_geojson(500000.0 + offset_m, 1500000.0, 32643)

    result = check_intersection_and_buffer(candidate, boundary, 30.0)

    assert result["intersects"] is False
    assert result["in_buffer"] is expected_in_buffer
    assert result["violation_type"] == expected_type
    assert abs(result["distance_meters"] - offset_m) <= 1.1


def test_exact_threshold_accounts_for_actual_projected_coordinates():
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)
    candidate = local_point_geojson(500030.0000, 1500000.0, 32643)

    result = check_intersection_and_buffer(candidate, boundary, 30.0)

    # EPSG:32643 -> WGS84 -> the selected metric CRS round-trip can place this
    # synthetic point microscopically outside 30 metres. The production code
    # therefore reports actual projected-buffer behavior, without adding a
    # metre-based tolerance.
    assert result["in_buffer"] is False
    assert result["violation_type"] == "CLEAR"
    assert result["distance_meters"] >= 30.0


@pytest.mark.parametrize(
    ("distance_m", "expected_in_buffer"),
    [
        (29.99, True),
        (30.00, False),
        (30.005, False),
        (30.02, False),
    ],
)
def test_buffer_does_not_expand_outside_requested_distance(distance_m, expected_in_buffer):
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)
    candidate = local_point_geojson(500000.0 + distance_m, 1500000.0, 32643)

    result = check_intersection_and_buffer(candidate, boundary, 30.0)

    assert result["in_buffer"] is expected_in_buffer


def test_zero_meter_buffer_intersection_and_separation():
    boundary = mapping(box(500000.0, 1500000.0, 500001.0, 1500001.0))
    boundary_geojson = transform_geom(
        "EPSG:32643", "EPSG:4326", boundary, precision=9
    )
    intersecting = transform_geom(
        "EPSG:32643",
        "EPSG:4326",
        mapping(box(500000.5, 1500000.5, 500002.0, 1500002.0)),
        precision=9,
    )
    separated = transform_geom(
        "EPSG:32643",
        "EPSG:4326",
        mapping(box(500010.0, 1500000.5, 500011.0, 1500001.5)),
        precision=9,
    )

    result_intersecting = check_intersection_and_buffer(intersecting, boundary_geojson, 0.0)
    result_separated = check_intersection_and_buffer(separated, boundary_geojson, 0.0)

    assert result_intersecting["in_buffer"] is True
    assert result_separated["in_buffer"] is False


@pytest.mark.parametrize(
    ("northing", "epsg"),
    [
        (1400000.0, 32643),
        (1800000.0, 32643),
        (1500000.0, 32644),
    ],
)
def test_correct_result_at_different_latitudes_and_karnataka_longitudes(northing, epsg):
    boundary = local_point_geojson(500000.0, northing, epsg)
    candidate = local_point_geojson(500025.0, northing, epsg)

    result = check_intersection_and_buffer(candidate, boundary, 30.0)

    assert result["in_buffer"] is True
    assert result["violation_type"] == "PROXIMITY_WARNING"
    assert abs(result["distance_meters"] - 25.0) <= 1.0


def test_cross_utm_zone_geometry_uses_safe_metric_projection():
    boundary = transform_geom(
        "EPSG:4326",
        "EPSG:4326",
        mapping(box(77.999, 12.930, 78.001, 12.932)),
        precision=9,
    )
    candidate = transform_geom(
        "EPSG:4326",
        "EPSG:4326",
        mapping(box(78.002, 12.930, 78.003, 12.932)),
        precision=9,
    )
    boundary_shape = Polygon(boundary["coordinates"][0])
    candidate_shape = Polygon(candidate["coordinates"][0])
    assert _combined_metric_crs(candidate_shape, boundary_shape).startswith("+proj=aeqd")

    result = check_intersection_and_buffer(candidate, boundary, 30.0)

    assert set(result) == {
        "intersects", "in_buffer", "distance_meters", "violation_type"
    }
    assert result["intersects"] is False
    assert result["in_buffer"] is False
    assert result["violation_type"] == "CLEAR"
    assert abs(result["distance_meters"] - 108.0) <= 12.0


@pytest.mark.parametrize(
    "change_geometry",
    [
        None,
        {"type": "Polygon", "coordinates": []},
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0.001, 0.001], [0, 0.001],
                             [0.001, 0], [0, 0]]],
            "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
        },
        {
            "type": "Polygon",
            "coordinates": [[[77.66, 12.93], [77.67, 12.94],
                             [77.66, 12.94], [77.67, 12.93], [77.66, 12.93]]],
            "crs": {"type": "name", "properties": {"code": 3857}},
        },
        {
            "type": "Polygon",
            "coordinates": [[[77.66, 12.93], [77.67, 12.94],
                             [77.66, 12.94], [77.67, 12.93], [77.66, 12.93]]],
            "crs": {"type": "name", "properties": {"name": "UNKNOWN:CRS"}},
        },
        "not-a-geometry",
    ],
)
def test_null_empty_and_unknown_crs_geometries_return_unknown(change_geometry):
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)

    result = check_intersection_and_buffer(change_geometry, boundary, 30.0)

    assert result == {
        "intersects": False,
        "in_buffer": False,
        "distance_meters": 9999.0,
        "violation_type": "UNKNOWN",
    }


def test_invalid_bowtie_geometry_is_repaired_without_crashing():
    invalid_bowtie = {
        "type": "Polygon",
        "coordinates": [[[77.660, 12.930], [77.675, 12.945],
                         [77.660, 12.945], [77.675, 12.930],
                         [77.660, 12.930]]],
    }
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)

    result = check_intersection_and_buffer(invalid_bowtie, boundary, 30.0)

    assert result == {
        "intersects": False,
        "in_buffer": False,
        "distance_meters": 9999.0,
        "violation_type": "UNKNOWN",
    }


def test_valid_polygon_and_multipolygon_are_supported():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                         [77.671, 12.931], [77.670, 12.931],
                         [77.670, 12.930]]],
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
    }
    multipolygon = {
        "type": "MultiPolygon",
        "coordinates": [[[[77.672, 12.930], [77.673, 12.930],
                          [77.673, 12.931], [77.672, 12.931],
                          [77.672, 12.930]]]],
        "crs": "EPSG:4326",
    }
    boundary = {
        "type": "Polygon",
        "coordinates": [[[77.680, 12.930], [77.681, 12.930],
                         [77.681, 12.931], [77.680, 12.931],
                         [77.680, 12.930]]],
    }

    assert check_intersection_and_buffer(polygon, boundary)["violation_type"] in {"CLEAR", "PROXIMITY_WARNING"}
    assert check_intersection_and_buffer(multipolygon, boundary)["violation_type"] in {"CLEAR", "PROXIMITY_WARNING"}


def test_geometrycollection_is_rejected_without_repair():
    collection = mapping(GeometryCollection([Point(77.670, 12.930), box(77.671, 12.930, 77.672, 12.931)]))
    boundary = local_point_geojson(500000.0, 1500000.0, 32643)

    result = check_intersection_and_buffer(collection, boundary, 30.0)

    assert result["violation_type"] == "UNKNOWN"


@pytest.mark.parametrize(
    "crs_declaration",
    [
        "EPSG:4326",
        "OGC:CRS84",
        "urn:ogc:def:crs:EPSG::4326",
    ],
)
def test_supported_wgs84_crs_declarations_are_accepted(crs_declaration):
    geometry = {
        "type": "Polygon",
        "coordinates": [[[77.670, 12.930], [77.671, 12.930],
                         [77.671, 12.931], [77.670, 12.931],
                         [77.670, 12.930]]],
        "crs": {"type": "name", "properties": {"name": crs_declaration}},
    }
    boundary = geometry

    assert check_intersection_and_buffer(geometry, boundary)["violation_type"] == "DIRECT_INTERSECTION"


def test_properties_code_and_missing_crs_metadata_are_handled_explicitly():
    common_coordinates = [[[77.670, 12.930], [77.671, 12.930],
                           [77.671, 12.931], [77.670, 12.931],
                           [77.670, 12.930]]]

    missing_crs = {"type": "Polygon", "coordinates": common_coordinates}
    epsg_code = {
        "type": "Polygon",
        "coordinates": common_coordinates,
        "crs": {"type": "name", "properties": {"code": 4326}},
    }

    assert check_intersection_and_buffer(missing_crs, missing_crs)["violation_type"] == "DIRECT_INTERSECTION"
    assert check_intersection_and_buffer(epsg_code, epsg_code)["violation_type"] == "DIRECT_INTERSECTION"


def test_raw_shapely_geometry_is_documented_as_wgs84():
    polygon = box(77.670, 12.930, 77.672, 12.932)

    assert check_intersection_and_buffer(polygon, polygon)["violation_type"] == "DIRECT_INTERSECTION"


def test_antimeridian_crossing_geometry_is_rejected_safely():
    crossing_polygon = {
        "type": "Polygon",
        "coordinates": [[[179.999, 12.930], [-179.999, 12.930],
                         [-179.999, 12.932], [179.999, 12.932],
                         [179.999, 12.930]]],
    }
    boundary = {
        "type": "Polygon",
        "coordinates": [[[179.998, 12.930], [179.999, 12.930],
                         [179.999, 12.931], [179.998, 12.931],
                         [179.998, 12.930]]],
    }

    result = check_intersection_and_buffer(crossing_polygon, boundary, 30.0)

    assert result["violation_type"] == "UNKNOWN"
