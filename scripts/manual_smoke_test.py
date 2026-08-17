#!/usr/bin/env python3
"""Test property submission script - submits test data to backend API."""
import json
import requests
import sys
from pathlib import Path
from datetime import date

BASE_URL = "http://localhost:8000"

# Test property data matching the form
test_submission = {
    "property_id": "TEST-0001",
    "address": "123 Main Street",
    "city": "Seattle",
    "state": "WA",
    "zip": "98101",
    "latitude": 47.6062,
    "longitude": -122.3321,
    "construction_type": "Frame",
    "year_built": 1985,
    "roof_type": "Built-up",
    "roof_age_years": 15,
    "square_footage": 50000,
    "occupancy_type": "Office",
    "num_stories": 3,
    "sprinkler_system": "Y",
    "cat_zone": "Wind",
    "distance_to_coast_miles": 45.5,
    "distance_to_fire_zone_miles": 12.3,
    "prior_claims_count_5yr": 1,
    "prior_claims_total_amount": 25000.00,
    "tiv": 5000000.00,
    "submission_date": str(date.today()),
}

# Upload the test image if it exists
image_path = Path("data/raw/images/test_property.jpg")
if not image_path.exists():
    print("ERROR: Test image not found at data/raw/images/test_property.jpg")
    sys.exit(1)

try:
    # Prepare multipart form data
    files = {"image": open(image_path, "rb")}
    data = test_submission
    
    print("Submitting test property to backend...")
    print(f"Property ID: {data['property_id']}")
    print(f"Address: {data['address']}, {data['city']}, {data['state']}")
    print(f"Image: {image_path}")
    print()
    
    # POST to the backend
    response = requests.post(f"{BASE_URL}/underwrite/submit", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("=" * 80)
        print("BACKEND RESPONSE (Full JSON)")
        print("=" * 80)
        print(json.dumps(result, indent=2))
        print("=" * 80)
        print()
        
        # Extract and display key components
        if "extracted_features" in result:
            print("\n--- EXTRACTED FEATURES ---")
            print(json.dumps(result["extracted_features"], indent=2))
        
        if "guideline_chunks" in result:
            print("\n--- GUIDELINE CHUNKS ---")
            print(json.dumps(result["guideline_chunks"], indent=2))
        
        if "risk_breakdown" in result:
            print("\n--- RISK BREAKDOWN ---")
            print(json.dumps(result["risk_breakdown"], indent=2))
        
        if "comparables" in result:
            print("\n--- COMPARABLES ---")
            print(json.dumps(result["comparables"], indent=2))
        
        if "decision" in result:
            print("\n--- DECISION ---")
            print(json.dumps(result["decision"], indent=2))
        
        if "memo_markdown" in result:
            print("\n--- MEMO MARKDOWN ---")
            print(result["memo_markdown"])
        
        print("\n✓ Submission successful!")
    else:
        print(f"ERROR: Request failed with status {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)

except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to backend at http://localhost:8000")
    print("Make sure uvicorn is running: uvicorn app.api.main:app --host 0.0.0.0 --port 8000")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
