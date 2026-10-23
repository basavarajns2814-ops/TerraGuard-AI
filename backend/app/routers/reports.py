from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import Alert, DetectedChange, MonitoringZone
from app.core.deps import get_current_user
from app.services.report_service import generate_csv_report, generate_pdf_report

router = APIRouter(prefix="/api/reports", tags=["Reports & Analytics"])

@router.get("/summary")
def get_reports_summary(
    zone_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Alert)
    if zone_id:
        query = query.filter(Alert.zone_id == zone_id)
    alerts = query.all()

    total_alerts = len(alerts)
    by_status = {}
    by_risk = {}
    by_category = {}
    total_area_sqm = 0.0

    for a in alerts:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_risk[a.risk_level] = by_risk.get(a.risk_level, 0) + 1
        by_category[a.category] = by_category.get(a.category, 0) + 1
        total_area_sqm += a.affected_area_sqm

    return {
        "total_alerts": total_alerts,
        "total_affected_area_sqm": round(total_area_sqm, 2),
        "total_affected_area_hectares": round(total_area_sqm / 10000.0, 4),
        "by_status": by_status,
        "by_risk": by_risk,
        "by_category": by_category,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }

@router.get("/export-csv")
def export_csv_report(
    zone_id: Optional[int] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Alert)
    if zone_id:
        query = query.filter(Alert.zone_id == zone_id)
    if status:
        query = query.filter(Alert.status == status)
    if risk_level:
        query = query.filter(Alert.risk_level == risk_level)
    alerts = query.order_by(Alert.risk_score.desc()).all()

    csv_content = generate_csv_report(alerts)
    filename = f"terraguard_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export-pdf")
def export_pdf_report(
    zone_id: Optional[int] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Alert)
    if zone_id:
        query = query.filter(Alert.zone_id == zone_id)
    if status:
        query = query.filter(Alert.status == status)
    if risk_level:
        query = query.filter(Alert.risk_level == risk_level)
    alerts = query.order_by(Alert.risk_score.desc()).all()

    pdf_bytes = generate_pdf_report(alerts)
    filename = f"terraguard_intelligence_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
