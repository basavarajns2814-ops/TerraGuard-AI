from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import DetectedChange, TemporalObservation

def track_temporal_evolution(
    db: Session,
    change: DetectedChange,
    new_area_sqm: float,
    observation_date: str,
    risk_score: float,
    confidence_score: float,
    image_url: str = None,
    scene_id: int = None
) -> str:
    """
    Updates temporal observation timeline for a candidate change
    and determines whether it is EXPANDING, STABLE, DISAPPEARING, or NEW.
    """
    # Create observation record
    obs = TemporalObservation(
        change_id=change.id,
        observation_date=observation_date,
        area_sqm=new_area_sqm,
        risk_score=risk_score,
        confidence_score=confidence_score,
        image_url=image_url,
        scene_id=scene_id,
        created_at=datetime.utcnow()
    )
    db.add(obs)

    # Calculate trend
    observations = db.query(TemporalObservation).filter(
        TemporalObservation.change_id == change.id
    ).order_by(TemporalObservation.observation_date.asc()).all()

    obs_count = len(observations) + 1 # including current
    change.observation_count = obs_count
    change.latest_observed_date = observation_date

    if obs_count <= 1:
        change.trend = "NEW"
    else:
        initial_area = observations[0].area_sqm if observations else new_area_sqm
        if initial_area > 0:
            growth_pct = ((new_area_sqm - initial_area) / initial_area) * 100.0
            if growth_pct >= 15.0:
                change.trend = "EXPANDING"
            elif growth_pct <= -30.0:
                change.trend = "DISAPPEARING"
            else:
                change.trend = "STABLE"
        else:
            change.trend = "STABLE"

    db.commit()
    return change.trend
