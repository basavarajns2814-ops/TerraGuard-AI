from typing import List, Dict, Any, Tuple

def evaluate_risk_and_confidence(
    category: str,
    affected_area_sqm: float,
    intersects_restricted: bool,
    restricted_zone_name: str = None,
    proximity_meters: float = 9999.0,
    observation_count: int = 1,
    trend: str = "NEW",
    cloud_coverage_percentage: float = 0.0,
    parcel_owner_type: str = "GOVERNMENT"
) -> Tuple[float, str, float, List[str]]:
    """
    Transparent, explainable risk assessment engine for land monitoring.
    Returns:
        (risk_score, risk_level, confidence_score, risk_reasons)
    """
    reasons: List[str] = []
    base_score = 40.0
    confidence = 0.88

    # 1. Category baseline
    if category == "WATER_BODY_ENCROACHMENT":
        base_score += 25.0
        reasons.append("Critical category: Detected alteration inside or adjacent to designated water body")
    elif category == "NEW_CONSTRUCTION":
        base_score += 20.0
        reasons.append("Detected new structural building footprint candidate")
    elif category == "EXPANSION":
        base_score += 18.0
        reasons.append("Structural footprint expanding beyond previous observation perimeter")
    elif category == "ROAD_BUFFER_VIOLATION":
        base_score += 15.0
        reasons.append("Change detected within reserved public highway right-of-way")
    elif category == "VEGETATION_LOSS":
        base_score += 10.0
        reasons.append("Significant green canopy reduction / land clearing detected")
    else:
        base_score += 5.0
        reasons.append("Unclassified surface reflectance shift")

    # 2. Restricted Boundary Intersections
    if intersects_restricted:
        base_score += 25.0
        zone_desc = f" ({restricted_zone_name})" if restricted_zone_name else ""
        reasons.append(f"Direct spatial intersection with legally protected restricted boundary{zone_desc}")
    elif proximity_meters < 50.0:
        base_score += 12.0
        reasons.append(f"Proximity warning: Candidate change is within {proximity_meters:.1f}m buffer of protected boundary")

    # 3. Parcel Ownership Status
    if parcel_owner_type in ["GOVERNMENT", "PUBLIC_RESERVE", "FOREST"]:
        base_score += 10.0
        reasons.append(f"Land tenure check: Parcel registered as {parcel_owner_type.replace('_', ' ').title()}")

    # 4. Area Magnitude
    if affected_area_sqm >= 1500.0:
        base_score += 15.0
        reasons.append(f"Extensive affected area ({affected_area_sqm:.1f} m² / {affected_area_sqm/10000.0:.2f} ha)")
    elif affected_area_sqm >= 500.0:
        base_score += 8.0
        reasons.append(f"Moderate candidate footprint ({affected_area_sqm:.1f} m²)")

    # 5. Multi-date Persistence and Trend
    if observation_count >= 3:
        base_score += 12.0
        reasons.append(f"High temporal persistence: Confirmed across {observation_count} distinct satellite acquisition dates")
    elif observation_count == 2:
        base_score += 6.0
        reasons.append("Temporal persistence: Re-observed on consecutive acquisition passes")

    if trend == "EXPANDING":
        base_score += 10.0
        reasons.append("Active growth trend: Spatial footprint progressively enlarging")

    # 6. Environmental Confidence Modifiers (Clouds, shadows)
    if cloud_coverage_percentage > 20.0:
        confidence -= 0.25
        base_score -= 8.0
        reasons.append(f"Confidence reduced: Image scene has {cloud_coverage_percentage:.1f}% cloud contamination")
    elif cloud_coverage_percentage > 5.0:
        confidence -= 0.10

    # Clamp scores
    risk_score = round(max(5.0, min(98.0, base_score)), 1)
    confidence_score = round(max(0.40, min(0.96, confidence)), 2)

    # Determine risk level
    if risk_score >= 80.0:
        risk_level = "CRITICAL"
    elif risk_score >= 65.0:
        risk_level = "HIGH"
    elif risk_score >= 40.0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return (risk_score, risk_level, confidence_score, reasons)
