from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

from faker import Faker
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DB_PATH, RAW_DIR

fake = Faker()

CONSTRUCTION_TYPES = [
    "Frame",
    "Joisted Masonry",
    "Non-Combustible",
    "Masonry Non-Combustible",
    "Fire Resistive",
]
OCCUPANCY_TYPES = ["Office", "Retail", "Warehouse", "Industrial", "Mixed-Use", "Multifamily"]
CAT_ZONES = ["Wind", "Hail", "Wildfire", "Flood", "Earthquake", "None"]
POLICY_TYPES = ["SFSP", "Bharat Sookshma Udyam Suraksha", "Bharat Laghu Udyam Suraksha"]


def build_properties_csv(path: Path, count: int = 300) -> None:
    rows = []
    for i in range(1, count + 1):
        construction = CONSTRUCTION_TYPES[i % len(CONSTRUCTION_TYPES)]
        occupancy = OCCUPANCY_TYPES[i % len(OCCUPANCY_TYPES)]
        cat_zone = CAT_ZONES[i % len(CAT_ZONES)]
        policy_type = POLICY_TYPES[i % len(POLICY_TYPES)]
        seismic_zone = "V" if i % 25 == 0 else "IV" if i % 15 == 0 else "II" if i % 3 else "III"
        roof_age = (i * 7) % 45
        prior_claims = (i * 3) % 6
        total_value_at_risk_inr = 2_000_000 + ((i * 137) % 55_000_000)
        row = {
            "property_id": f"PROP-{i:04d}",
            "address": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip": fake.postcode(),
            "latitude": round(fake.latitude(), 6),
            "longitude": round(fake.longitude(), 6),
            "construction_type": construction,
            "year_built": 1960 + (i % 65),
            "roof_type": "Built-up" if i % 2 else "Modified Bitumen",
            "roof_age_years": roof_age,
            "square_footage": 35_000 + ((i * 73) % 120_000),
            "occupancy_type": occupancy,
            "num_stories": 1 + (i % 12),
            "sprinkler_system": "Y" if i % 3 else "N",
            "cat_zone": cat_zone,
            "policy_type": policy_type,
            "seismic_zone": seismic_zone,
            "total_value_at_risk_inr": round(float(total_value_at_risk_inr), 2),
            "distance_to_coast_miles": round((i * 13) % 80 + (0.5 * (i % 3)), 1),
            "distance_to_fire_zone_miles": round((i * 11) % 50 + (0.4 * (i % 4)), 1),
            "prior_claims_count_5yr": prior_claims,
            "prior_claims_total_amount": round(float(prior_claims) * 12000 + (i * 450), 2),
            "tiv": round(float(total_value_at_risk_inr), 2),
            "submission_date": fake.date_between(start_date='-2y', end_date='today').isoformat(),
        }
        rows.append(row)

    fieldnames = [
        "property_id",
        "address",
        "city",
        "state",
        "zip",
        "latitude",
        "longitude",
        "construction_type",
        "year_built",
        "roof_type",
        "roof_age_years",
        "square_footage",
        "occupancy_type",
        "num_stories",
        "sprinkler_system",
        "cat_zone",
        "policy_type",
        "seismic_zone",
        "total_value_at_risk_inr",
        "distance_to_coast_miles",
        "distance_to_fire_zone_miles",
        "prior_claims_count_5yr",
        "prior_claims_total_amount",
        "tiv",
        "submission_date",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def seed_sqlite_properties(path: Path) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                property_id TEXT PRIMARY KEY,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                latitude REAL,
                longitude REAL,
                construction_type TEXT,
                year_built INTEGER,
                roof_type TEXT,
                roof_age_years INTEGER,
                square_footage INTEGER,
                occupancy_type TEXT,
                num_stories INTEGER,
                sprinkler_system TEXT,
                cat_zone TEXT,
                distance_to_coast_miles REAL,
                distance_to_fire_zone_miles REAL,
                prior_claims_count_5yr INTEGER,
                prior_claims_total_amount REAL,
                tiv REAL,
                submission_date TEXT
            )
            """
        )
        with path.open("r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO properties (
                        property_id, address, city, state, zip, latitude, longitude,
                        construction_type, year_built, roof_type, roof_age_years,
                        square_footage, occupancy_type, num_stories, sprinkler_system,
                        cat_zone, distance_to_coast_miles, distance_to_fire_zone_miles,
                        prior_claims_count_5yr, prior_claims_total_amount, tiv, submission_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["property_id"], row["address"], row["city"], row["state"], row["zip"],
                        float(row["latitude"]), float(row["longitude"]), row["construction_type"], int(row["year_built"]),
                        row["roof_type"], int(row["roof_age_years"]), int(row["square_footage"]), row["occupancy_type"],
                        int(row["num_stories"]), row["sprinkler_system"], row["cat_zone"], float(row["distance_to_coast_miles"]),
                        float(row["distance_to_fire_zone_miles"]), int(row["prior_claims_count_5yr"]), float(row["prior_claims_total_amount"]),
                        float(row["tiv"]), row["submission_date"],
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def build_underwriting_guidelines_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create PDF with proper text wrapping using SimpleDocTemplate and Paragraphs
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Get default styles and create custom title style
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='black',
        spaceAfter=20,
        alignment=0,  # Left align
    )
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=14,
        spaceAfter=12,
        alignment=4,  # Justified
    )

    # Build the story (list of flowable objects)
    story = []

    # Title
    story.append(Paragraph("Underwriting Guidelines & Appetite", title_style))
    story.append(Spacer(1, 0.2 * inch))

    # Content sections with proper wrapping
    sections = [
        ("1. Construction & Occupancy Risk",
         "Frame construction and higher-hazard occupancies such as Warehouse and Industrial merit additional underwriting scrutiny. Buildings without sprinkler coverage in these occupancies warrant elevated risk consideration. The presence or absence of active fire suppression systems directly impacts the underwriting decision. Properties with combustible framing in high-value occupancies require careful evaluation of replacement cost and loss potential."),

        ("2. Roof Age Thresholds",
         "Roofs older than 20 years are considered aging and may trigger referral reviews. Roofs older than 30 years warrant stronger concern and are likely to require replacement planning or mitigation before renewal. The age of the roof significantly affects both loss frequency and severity. Modern roofing materials provide better wind and weather resistance compared to aged materials. Documentation of recent roof maintenance or replacement is favorable for underwriting decisions."),

        ("3. CAT Zone Appetite",
         "Exposure in wildfire, flood, or wind zones materially increases risk and is not generally considered low risk. Proximity to coast or interface areas compounds this concern. Properties located within designated catastrophe exposure zones require enhanced scrutiny and may command higher premiums or stricter underwriting requirements. Natural disaster exposure is a primary driver of overall risk classification."),

        ("4. Prior Loss History Appetite",
         "Properties with more than two prior claims in five years suggest a negative loss pattern and should be reviewed for adverse loss history and pricing implications. Frequency of losses is more concerning than severity in many cases. A history of multiple claims indicates potential maintenance issues, operational risks, or problematic property conditions that warrant close attention during underwriting."),

        ("5. TIV Concentration Limits",
         "Total insured value above USD 20 million requires enhanced risk review because of concentration exposure and more significant loss severity. Large single-location concentrations of value create potential for catastrophic loss. Properties with very high TIV require additional scrutiny regarding building condition, occupancy hazards, and business continuity considerations."),

        ("6. Referral vs Decline Criteria",
         "Scores from 0 to 30 are generally acceptable for approval. Scores 31 to 60 warrant referral for further review by senior underwriters. Scores 61 to 84 are decline candidates where mitigation measures may reduce the exposure and allow for reconsideration. Scores 85 to 100 are auto-decline based on the combined risk profile and require exceptional circumstances for override. The system uses deterministic underwriting rules to produce a score from 0 to 100, with additive rules applied consistently across all applications."),
    ]

    for section_title, section_text in sections:
        story.append(Paragraph(section_title, styles['Heading2']))
        story.append(Paragraph(section_text, body_style))
        story.append(Spacer(1, 0.1 * inch))

    # Build the PDF
    doc.build(story)


if __name__ == "__main__":
    build_properties_csv(RAW_DIR / "properties.csv", count=300)
    seed_sqlite_properties(RAW_DIR / "properties.csv")
    build_underwriting_guidelines_pdf(RAW_DIR / "underwriting_guidelines.pdf")
    print("Generated synthetic property data, seeded SQLite, and underwriting PDF.")
