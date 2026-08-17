from __future__ import annotations

import json

import pandas as pd
import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="UW Risk Copilot", page_icon="🏢", layout="wide")


with st.sidebar:
    st.title("UW Risk Copilot")
    st.caption("AI-assisted commercial property underwriting risk assistant")


def render_decision_badge(decision: str) -> None:
    palette = {
        "Accept": "#2e7d32",
        "Refer": "#b26a00",
        "Decline": "#e66a00",
        "Decline (mitigation possible)": "#e66a00",
        "Auto-Decline": "#c62828",
    }
    color = palette.get(decision, "#616161")
    st.markdown(f"<span style='background:{color};color:white;padding:8px 12px;border-radius:8px;display:inline-block'>{decision}</span>", unsafe_allow_html=True)


new_submission_tab, portfolio_tab = st.tabs(["New Submission", "Portfolio View"])

with new_submission_tab:
    with st.form("submission_form"):
        col1, col2 = st.columns(2)
        with col1:
            property_id = st.text_input("Property ID")
            address = st.text_input("Address")
            city = st.text_input("City")
            state = st.text_input("State")
            zip_code = st.text_input("ZIP")
            latitude = st.number_input("Latitude", value=37.7749, format="%.6f", key="submission_latitude")
            longitude = st.number_input("Longitude", value=-122.4194, format="%.6f", key="submission_longitude")
            construction_type = st.selectbox("Construction Type", ["Frame", "Joisted Masonry", "Non-Combustible", "Masonry Non-Combustible", "Fire Resistive"])
            year_built = st.number_input("Year Built", min_value=1900, max_value=2100, value=1995, step=1)
            roof_type = st.text_input("Roof Type", value="") or None
            roof_age_years = st.number_input("Roof Age Years", min_value=0, max_value=100, value=None, step=1)
            square_footage = st.number_input("Square Footage", min_value=1, max_value=10000000, value=120000, step=100)
        with col2:
            occupancy_type = st.selectbox("Occupancy Type", ["Office", "Retail", "Warehouse", "Industrial", "Mixed-Use", "Multifamily", "Restaurant"], key="submission_occupancy_type")
            num_stories = st.number_input("Number of Stories", min_value=1, max_value=80, value=4)
            sprinkler_system = st.selectbox("Sprinkler System", ["Y", "N"])
            cat_zone = st.selectbox("CAT Zone", ["Wind", "Hail", "Wildfire", "Flood", "Earthquake", "None"])
            rsmd_cover = st.checkbox("Riot / Strike / Malicious Damage (RSMD) Cover")
            seismic_zone = st.selectbox("Seismic Zone", ["II", "III", "IV", "V"], index=0)
            distance_to_coast_miles = st.number_input("Distance to Coast (mi)", min_value=0.0, max_value=1000.0, value=None, step=0.1)
            distance_to_fire_zone_miles = st.number_input("Distance to Fire Zone (mi)", min_value=0.0, max_value=1000.0, value=None, step=0.1)
            prior_claims_count_5yr = st.number_input("Prior Claims (5Y)", min_value=0, max_value=20, value=None, step=1)
            prior_claims_total_amount = st.number_input("Prior Claims Total Amount", min_value=0.0, max_value=50000000.0, value=None, step=100.0)
            tiv = st.number_input("Total Value at Risk (₹)", min_value=0.0, max_value=100000000000.0, value=5500000.0)
            if tiv <= 50_000_000:
                indicative_segment = "Bharat Sookshma Udyam Suraksha"
            elif tiv <= 500_000_000:
                indicative_segment = "Bharat Laghu Udyam Suraksha"
            else:
                indicative_segment = "Larger-risk/commercial property segment"
            st.caption(f"Indicative Product Segment: {indicative_segment}")
            st.caption("Indicative classification only; final product selection is subject to insurer underwriting and product eligibility.")
            submission_date = st.date_input("Submission Date")
            uploaded_images = st.file_uploader(
                "Property images",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
            )
            if uploaded_images:
                preview_columns = st.columns(min(len(uploaded_images), 4))
                for index, uploaded_image in enumerate(uploaded_images):
                    with preview_columns[index % len(preview_columns)]:
                        try:
                            st.image(uploaded_image, caption=f"Image {index + 1}", width=180)
                        except Exception as exc:
                            st.error(f"Could not preview {uploaded_image.name}: {exc}")
                if len(uploaded_images) > 1:
                    st.caption("Multiple images selected; current underwriting API processes one image per submission.")
        submitted = st.form_submit_button("Run underwriting review")

    if submitted:
        current_year = pd.Timestamp.now().year
        if roof_age_years is not None and roof_age_years < 0:
            st.error("Roof age must be zero or greater.")
            st.stop()
        if square_footage <= 0:
            st.error("Square footage must be greater than zero.")
            st.stop()
        if not 1800 <= year_built <= current_year:
            st.error(f"Year built must be between 1800 and {current_year}.")
            st.stop()
        if tiv <= 0:
            st.error("TIV must be greater than zero.")
            st.stop()

        files = {}
        if uploaded_images:
            uploaded_image = uploaded_images[0]
            files = {"image": (uploaded_image.name, uploaded_image.getvalue(), uploaded_image.type or "application/octet-stream")}
        payload = {
            "property_id": property_id,
            "address": address,
            "city": city,
            "state": state,
            "zip": str(zip_code),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "construction_type": construction_type,
            "year_built": int(year_built),
            "roof_type": roof_type,
            "roof_age_years": int(roof_age_years) if roof_age_years is not None else None,
            "square_footage": int(square_footage),
            "occupancy_type": occupancy_type,
            "num_stories": int(num_stories),
            "sprinkler_system": sprinkler_system,
            "cat_zone": cat_zone,
            "rsmd_cover": rsmd_cover,
            "seismic_zone": seismic_zone,
            "distance_to_coast_miles": float(distance_to_coast_miles) if distance_to_coast_miles is not None else None,
            "distance_to_fire_zone_miles": float(distance_to_fire_zone_miles) if distance_to_fire_zone_miles is not None else None,
            "prior_claims_count_5yr": int(prior_claims_count_5yr) if prior_claims_count_5yr is not None else None,
            "prior_claims_total_amount": float(prior_claims_total_amount) if prior_claims_total_amount is not None else None,
            "tiv": float(tiv),
            "submission_date": str(submission_date),
        }

        try:
            with st.spinner("Running underwriting analysis..."):
                response = requests.post(f"{BACKEND_URL}/underwrite/submit", data=payload, files=files, timeout=120)
            response.raise_for_status()
            data = response.json()
            st.subheader("Results")
            col3, col4 = st.columns([1, 3])
            with col3:
                st.metric("Risk Score", data.get("risk_score", 0))
                render_decision_badge(data.get("decision", "Accept"))
                if data.get("risk_flags"):
                    st.write("Flags:")
                    for flag in data["risk_flags"]:
                        st.code(flag)
            with col4:
                st.caption(f"Indicative Product Segment: {data.get('policy_type', indicative_segment)}")
                st.caption("Indicative classification only; final product selection is subject to insurer underwriting and product eligibility.")
                image_data = data.get("extracted_features", {})
                st.markdown("### Image Review")
                st.write(f"Status: {image_data.get('image_status', 'Not submitted').title()}")
                if image_data.get("image_reason"):
                    st.write("Reason:")
                    st.write(image_data["image_reason"])
                st.write("Image-derived underwriting evidence:")
                st.write("Used" if image_data.get("image_risk_evidence_used") else "Not used")
                st.markdown("### AI Memo")
                st.write(f"Status: {data.get('ai_memo_status', 'Unavailable')}")
                if data.get("ai_memo_status") == "Unavailable":
                    st.write(f"Reason: {data.get('ai_memo_reason', 'Memo generation did not succeed.')}")
                else:
                    st.markdown(data["memo_markdown"])
            with st.expander("Debug response"):
                st.write("policy_type")
                st.write(data.get("policy_type"))
                st.write("total_value_at_risk_inr")
                st.write(data.get("total_value_at_risk_inr"))
                st.write("extracted_features")
                st.json(data.get("extracted_features", {}))
                st.write("guideline_chunks")
                st.json(data.get("guideline_chunks", []))
                st.write("memo_markdown")
                st.code(data.get("memo_markdown", ""), language="markdown")
        except Exception as exc:
            st.error(f"Submission failed: {exc}")

with portfolio_tab:
    try:
        response = requests.get(f"{BACKEND_URL}/underwrite/history", timeout=30)
        response.raise_for_status()
        records = response.json()
        if records:
            df = pd.DataFrame(records)
            decision_filter = st.selectbox("Filter by decision", ["All", *sorted({item.get("decision", "") for item in records if item.get("decision")})])
            if decision_filter != "All":
                df = df[df["decision"] == decision_filter]
            df = df.sort_values("risk_score", ascending=False)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No underwriting submissions yet.")
    except Exception as exc:
        st.error(f"Portfolio view could not load: {exc}")
