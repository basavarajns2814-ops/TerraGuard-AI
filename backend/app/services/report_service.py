import io
import csv
from datetime import datetime
from typing import List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models import Alert

def generate_csv_report(alerts: List[Alert]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Alert Code",
        "District",
        "Monitoring Zone",
        "Parcel Number",
        "Category",
        "Risk Level",
        "Risk Score",
        "Confidence",
        "Area (sqm)",
        "Area (ha)",
        "Centroid Lat",
        "Centroid Lng",
        "Status",
        "First Observed Date",
        "Latest Observed Date",
        "Assigned Officer",
        "Risk Reasons"
    ])

    for a in alerts:
        reasons_str = "; ".join(a.risk_reasons) if a.risk_reasons else ""
        writer.writerow([
            a.alert_code,
            a.zone.district if a.zone else "Bengaluru",
            a.zone.name if a.zone else "Zone",
            a.parcel.parcel_number if a.parcel else "N/A",
            a.category,
            a.risk_level,
            a.risk_score,
            a.confidence_score,
            a.affected_area_sqm,
            a.affected_area_hectares,
            a.centroid_lat,
            a.centroid_lng,
            a.status,
            a.first_observed_date,
            a.latest_observed_date,
            a.assigned_to.full_name if a.assigned_to else "Unassigned",
            reasons_str
        ])

    return output.getvalue()


def generate_pdf_report(alerts: List[Alert], report_title: str = "Land Encroachment & Change Monitoring Summary") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569')
    )
    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Italic'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#64748b')
    )

    story = []

    # Title & Header
    story.append(Paragraph("TerraGuard AI — Geospatial Land Monitoring System", title_style))
    story.append(Paragraph(f"{report_title} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", subtitle_style))
    story.append(Spacer(1, 15))

    # Summary Stats
    total_alerts = len(alerts)
    critical_count = sum(1 for a in alerts if a.risk_level == "CRITICAL")
    high_count = sum(1 for a in alerts if a.risk_level == "HIGH")
    total_area_ha = sum(a.affected_area_hectares for a in alerts)

    summary_data = [
        ["Total Alerts", "Critical Risk", "High Risk", "Total Candidate Area"],
        [str(total_alerts), str(critical_count), str(high_count), f"{total_area_ha:.2f} ha"]
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Detailed Table
    table_headers = ["Alert Code", "Zone / Parcel", "Category", "Risk", "Area (m²)", "Status"]
    table_rows = [table_headers]

    for a in alerts[:25]: # Page limit for clean PDF layout
        table_rows.append([
            a.alert_code,
            f"{a.zone.name if a.zone else 'Zone'}\n{a.parcel.parcel_number if a.parcel else ''}",
            a.category.replace('_', ' ').title(),
            f"{a.risk_level} ({a.risk_score:.0f})",
            f"{a.affected_area_sqm:.0f}",
            a.status.replace('_', ' ').title()
        ])

    alert_table = Table(table_rows, colWidths=[90, 140, 130, 80, 60, 80])
    alert_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')])
    ]))
    story.append(alert_table)
    story.append(Spacer(1, 25))

    # Disclaimer
    disclaimer_text = (
        "CONFIDENTIAL & REGULATORY ADVISORY: TerraGuard AI detections represent satellite-observed "
        "surface reflectance anomalies and geometric change candidates. Ground verification, cadastral boundary "
        "survey, and statutory officer confirmation are mandatory prior to initiating legal or enforcement action."
    )
    story.append(Paragraph(disclaimer_text, disclaimer_style))

    doc.build(story)
    return buffer.getvalue()
