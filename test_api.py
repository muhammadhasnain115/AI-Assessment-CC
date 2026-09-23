"""
Automated Test Suite for CareCloud Patient Registration API
Run with: pytest test_api.py -v
"""

from datetime import date, timedelta
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    """Verify system health endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["error"] is None
    assert json_data["data"]["status"] == "healthy"


def test_list_patients_envelope():
    """Verify GET /patients adheres to standard response envelope."""
    res = client.get("/patients")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert json_data["error"] is None
    assert isinstance(json_data["data"], list)
    assert len(json_data["data"]) >= 1


def test_filter_by_last_name():
    """Verify search filter by last_name works."""
    res = client.get("/patients?last_name=Hernandez")
    assert res.status_code == 200
    patients = res.json()["data"]
    assert len(patients) >= 1
    assert any(p["last_name"] == "Hernandez" for p in patients)


def test_search_by_name_and_pagination():
    """Verify search by name parameter and 10-patient pagination."""
    res = client.get("/patients?search=Jane&page=1&limit=10")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["error"] is None
    assert isinstance(json_data["data"], list)
    assert len(json_data["data"]) >= 1
    assert json_data["page"] == 1
    assert json_data["limit"] == 10
    assert "total" in json_data
    assert any(p["first_name"] == "Jane" for p in json_data["data"])


def test_validation_rejects_future_dob():
    """Validation: Reject future birth date with 422."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = client.post("/patients", json={
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": tomorrow,
        "sex": "Male",
        "phone_number": "3055550199",
        "address_line_1": "123 Main St",
        "city": "Miami",
        "state": "FL",
        "zip_code": "33101"
    })
    assert res.status_code == 422
    assert res.json()["data"] is None
    assert "future" in res.json()["error"].lower()


def test_validation_rejects_invalid_phone():
    """Validation: Reject invalid phone numbers with 422."""
    res = client.post("/patients", json={
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": "1990-01-01",
        "sex": "Female",
        "phone_number": "123", # Too short
        "address_line_1": "123 Main St",
        "city": "Miami",
        "state": "FL",
        "zip_code": "33101"
    })
    assert res.status_code == 422
    assert "phone" in res.json()["error"].lower()


def test_validation_rejects_invalid_state():
    """Validation: Reject invalid state abbreviation with 422."""
    res = client.post("/patients", json={
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": "1990-01-01",
        "sex": "Other",
        "phone_number": "3055550199",
        "address_line_1": "123 Main St",
        "city": "Miami",
        "state": "XX", # Invalid state
        "zip_code": "33101"
    })
    assert res.status_code == 422
    assert "state" in res.json()["error"].lower()


def test_full_patient_crud_lifecycle():
    """Complete CRUD cycle: Create -> Update -> Soft Delete -> 404 Check."""
    # 1. Create Patient (POST /patients)
    create_res = client.post("/patients", json={
        "first_name": "Alice",
        "last_name": "Smith",
        "date_of_birth": "1993-04-12",
        "sex": "Female",
        "phone_number": "4155550191",
        "address_line_1": "100 Pine Street",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94111",
        "insurance_provider": "UnitedHealthcare",
        "preferred_language": "English"
    })
    assert create_res.status_code == 201
    created = create_res.json()["data"]
    patient_id = created["patient_id"]
    assert created["first_name"] == "Alice"

    # 2. Update Patient (PUT /patients/{id})
    update_res = client.put(f"/patients/{patient_id}", json={
        "address_line_1": "200 Montgomery St",
        "city": "San Francisco"
    })
    assert update_res.status_code == 200
    assert update_res.json()["data"]["address_line_1"] == "200 Montgomery St"

    # 3. Soft Delete Patient (DELETE /patients/{id})
    del_res = client.delete(f"/patients/{patient_id}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["status"] == "soft_deleted"

    # 4. Verify soft-deleted patient is now excluded (404)
    get_res = client.get(f"/patients/{patient_id}")
    assert get_res.status_code == 404


def test_voice_tool_check_existing_patient():
    """Verify Voice AI tool check_existing_patient."""
    res = client.post("/check-patient", json={"phone_number": "2125550144"})
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["last_name"] == "Hernandez"


def test_voice_tool_register_and_update_patient():
    """Verify Voice AI tools register_patient and update_patient."""
    phone = "7865550123"
    # Register via tool
    reg_res = client.post("/register-patient", json={
        "first_name": "David",
        "last_name": "Miller",
        "date_of_birth": "1988-08-08",
        "sex": "Male",
        "phone_number": phone,
        "address_line_1": "555 Ocean Dr",
        "city": "Miami",
        "state": "FL",
        "zip_code": "33139"
    })
    assert reg_res.status_code == 200
    assert reg_res.json()["success"] is True

    # Update via tool
    upd_res = client.post("/update-patient", json={
        "phone_number": phone,
        "email": "david.miller@example.com"
    })
    assert upd_res.status_code == 200
    assert upd_res.json()["success"] is True

