"""
CareCloud Voice AI Agent - Patient Registration System
Single-file, clean, and production-ready backend service.

Architecture:
1. Environment & Supabase Database Client
2. Data Validation Models (Pydantic v2 - CareCloud Specs)
3. REST API Endpoints (/patients, /health, /dashboard)
4. Voice AI Tools & Webhooks (Retell AI Function Calling)
"""

import os
import re
import json
import logging
from enum import Enum
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("carecloud-api")

# =============================================================================
# 1. DATABASE CONNECTION (SUPABASE POSTGRESQL)
# =============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wxljcerqnivdpazaupuh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind4bGpjZXJxbml2ZHBhemF1cHVoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAxNzg3MDUsImV4cCI6MjEwNTc1NDcwNX0.3almwwudeprIX811B-1kXX_B6qFs6ACXzklzC9LBL8I"
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =============================================================================
# 2. VALIDATION MODELS (CARECLOUD SPECIFICATIONS)
# =============================================================================

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR"
}

NAME_REGEX = re.compile(r"^[A-Za-z'\-\s]{1,50}$")
ZIP_REGEX = re.compile(r"^\d{5}(-\d{4})?$")


def clean_phone(v: Optional[str]) -> Optional[str]:
    """Normalize phone number to 10 digits."""
    if not v:
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Phone number must be a valid 10-digit U.S. number.")
    return digits


class PatientSex(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE_TO_ANSWER = "Decline to Answer"


class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: date = Field(..., description="Valid date, not in future")
    sex: PatientSex
    phone_number: str = Field(..., description="Valid U.S. 10-digit phone number")
    address_line_1: str = Field(..., min_length=1, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2)
    zip_code: str = Field(...)
    email: Optional[EmailStr] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not NAME_REGEX.match(trimmed):
            raise ValueError("Name must be 1-50 chars and contain only letters, hyphens, or apostrophes.")
        return trimmed

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("Date of birth cannot be in the future.")
        try:
            min_date = today.replace(year=today.year - 8)
        except ValueError:
            min_date = today.replace(year=today.year - 8, day=28)
        if v > min_date:
            raise ValueError("Patient must be at least 8 years old.")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = clean_phone(v)
        if not cleaned:
            raise ValueError("10-digit phone number is required.")
        return cleaned

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        return clean_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        upper_v = v.strip().upper()
        if upper_v not in US_STATES:
            raise ValueError(f"Invalid U.S. state abbreviation: '{v}'.")
        return upper_v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        trimmed = v.strip()
        if not ZIP_REGEX.match(trimmed):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return trimmed


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[PatientSex] = None
    phone_number: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[EmailStr] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        trimmed = v.strip()
        if not NAME_REGEX.match(trimmed):
            raise ValueError("Name must be 1-50 chars and contain only letters, hyphens, or apostrophes.")
        return trimmed

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            today = date.today()
            if v > today:
                raise ValueError("Date of birth cannot be in the future.")
            try:
                min_date = today.replace(year=today.year - 8)
            except ValueError:
                min_date = today.replace(year=today.year - 8, day=28)
            if v > min_date:
                raise ValueError("Patient must be at least 8 years old.")
        return v

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return clean_phone(v)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        upper_v = v.strip().upper()
        if upper_v not in US_STATES:
            raise ValueError(f"Invalid state abbreviation: '{v}'.")
        return upper_v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: Optional[str]) -> Optional[str]:
        if v is None: return None
        trimmed = v.strip()
        if not ZIP_REGEX.match(trimmed):
            raise ValueError("ZIP code must be 5 digits (12345) or ZIP+4 (12345-6789).")
        return trimmed


class PatientRead(PatientBase):
    patient_id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    last_call_transcript: Optional[str] = None
    last_call_recording_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# 3. FASTAPI APP INITIALIZATION & ENVELOPE HANDLERS
# =============================================================================

app = FastAPI(
    title="CareCloud Patient Registration API",
    description="Voice AI Demographic Intake Backend",
    version="1.0.0",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CareCloud strict envelope: { "data": ..., "error": null }
def api_response(data: Any = None, error: Any = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": data, "error": error})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return api_response(data=None, error=exc.detail, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [f"{' -> '.join(str(i) for i in e.get('loc', []) if i != 'body')}: {e.get('msg')}" for e in exc.errors()]
    return api_response(data=None, error="; ".join(errors), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    return api_response(data=None, error="Internal server error", status_code=500)


# =============================================================================
# 4. REST API ENDPOINTS
# =============================================================================

@app.get("/patients", tags=["Patients"], summary="List All Active Patients")
def list_patients(
    response: Response,
    last_name: Optional[str] = Query(None, description="Filter by last name"),
    date_of_birth: Optional[str] = Query(None, description="Filter by DOB YYYY-MM-DD"),
    phone_number: Optional[str] = Query(None, description="Filter by 10-digit phone"),
    search: Optional[str] = Query(None, description="Search by name (first or last)"),
    name: Optional[str] = Query(None, description="Search by name alias"),
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Items per page (default 10)")
):
    query = supabase.table("patients").select("*", count="exact").is_("deleted_at", "null")
    
    search_query = (search or name or "").strip()
    if search_query:
        query = query.or_(f"first_name.ilike.%{search_query}%,last_name.ilike.%{search_query}%")
    if last_name:
        query = query.ilike("last_name", f"%{last_name.strip()}%")
    if date_of_birth:
        query = query.eq("date_of_birth", date_of_birth.strip())
    if phone_number:
        cleaned = clean_phone(phone_number)
        if cleaned:
            query = query.eq("phone_number", cleaned)

    query = query.order("created_at", desc=True)

    if page is not None or limit is not None:
        p = page if page is not None else 1
        l = limit if limit is not None else 10
        start = (p - 1) * l
        end = start + l - 1
        query = query.range(start, end)

    res = query.execute()
    total_count = res.count if res.count is not None else len(res.data or [])

    response.headers["X-Total-Count"] = str(total_count)
    if page:
        response.headers["X-Page"] = str(page)
    if limit:
        response.headers["X-Limit"] = str(limit)

    return {
        "data": res.data or [],
        "error": None,
        "total": total_count,
        "page": page or 1,
        "limit": limit or len(res.data or [])
    }


@app.get("/patients/{patient_id}", tags=["Patients"], summary="Get Single Patient")
def get_patient(patient_id: UUID):
    res = supabase.table("patients").select("*").eq("patient_id", str(patient_id)).is_("deleted_at", "null").execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Patient not found or deleted")
    return {"data": res.data[0], "error": None}


@app.post("/patients", tags=["Patients"], status_code=201, summary="Register New Patient")
def create_patient(patient_in: PatientCreate):
    payload = patient_in.model_dump()
    payload["date_of_birth"] = str(payload["date_of_birth"])
    payload["sex"] = payload["sex"].value if hasattr(payload["sex"], "value") else payload["sex"]
    
    res = supabase.table("patients").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to save patient record")
    return {"data": res.data[0], "error": None}


@app.put("/patients/{patient_id}", tags=["Patients"], summary="Update Patient Record")
def update_patient(patient_id: UUID, patient_update: PatientUpdate):
    # Verify patient exists
    check = supabase.table("patients").select("patient_id").eq("patient_id", str(patient_id)).is_("deleted_at", "null").execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Patient not found or deleted")

    updates = patient_update.model_dump(exclude_unset=True)
    if "date_of_birth" in updates and updates["date_of_birth"]:
        updates["date_of_birth"] = str(updates["date_of_birth"])
    if "sex" in updates and hasattr(updates["sex"], "value"):
        updates["sex"] = updates["sex"].value
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    res = supabase.table("patients").update(updates).eq("patient_id", str(patient_id)).execute()
    return {"data": res.data[0], "error": None}


@app.delete("/patients/{patient_id}", tags=["Patients"], summary="Soft-Delete Patient Record")
def delete_patient(patient_id: UUID):
    now_utc = datetime.now(timezone.utc).isoformat()
    res = supabase.table("patients").update({"deleted_at": now_utc}).eq("patient_id", str(patient_id)).is_("deleted_at", "null").execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Patient not found or already deleted")
    return {"data": {"patient_id": str(patient_id), "status": "soft_deleted"}, "error": None}


@app.get("/health", tags=["System"], summary="System Health Check")
def health_check():
    return {"data": {"status": "healthy", "database": "connected", "version": "1.0.0"}, "error": None}


# =============================================================================
# 5. VOICE AI TOOLS (RETELL AI INTEGRATION)
# =============================================================================

@app.post("/check-patient", include_in_schema=False)
async def check_patient(request: Request):
    """Retell AI Tool: Checks if caller already exists by phone number."""
    body = await request.json()
    args = body.get("args", body) if isinstance(body.get("args"), dict) else body
    phone = args.get("phone_number")
    cleaned = clean_phone(phone)
    if not cleaned:
        return {"exists": False, "message": "No valid phone number provided."}

    p = supabase.table("patients").select("*").eq("phone_number", cleaned).is_("deleted_at", "null").limit(1).execute()
    if p.data:
        pt = p.data[0]
        return {
            "exists": True,
            "patient_id": pt.get("patient_id"),
            "first_name": pt.get("first_name"),
            "last_name": pt.get("last_name"),
            "date_of_birth": str(pt.get("date_of_birth")),
            "sex": pt.get("sex"),
            "phone_number": pt.get("phone_number"),
            "address_line_1": pt.get("address_line_1"),
            "address_line_2": pt.get("address_line_2") or "",
            "city": pt.get("city"),
            "state": pt.get("state"),
            "zip_code": pt.get("zip_code"),
            "email": pt.get("email") or "None on file",
            "insurance_provider": pt.get("insurance_provider") or "None (Self-Pay)",
            "insurance_member_id": pt.get("insurance_member_id") or "None",
            "preferred_language": pt.get("preferred_language") or "English",
            "emergency_contact_name": pt.get("emergency_contact_name") or "None",
            "emergency_contact_phone": pt.get("emergency_contact_phone") or "None",
            "message": f"Found existing record for {pt.get('first_name')} {pt.get('last_name')}."
        }
    return {"exists": False, "message": "No record found for this phone number."}


@app.post("/register-patient", include_in_schema=False)
async def register_patient_tool(request: Request):
    """Retell AI Tool: Validates and saves new patient from voice call."""
    body = await request.json()
    args = body.get("args", body) if isinstance(body.get("args"), dict) else body
    try:
        patient_in = PatientCreate(**args)
        payload = patient_in.model_dump()
        payload["date_of_birth"] = str(payload["date_of_birth"])
        payload["sex"] = payload["sex"].value
        res = supabase.table("patients").insert(payload).execute()
        created = res.data[0]
        return {
            "success": True,
            "patient_id": created["patient_id"],
            "first_name": created["first_name"],
            "last_name": created["last_name"],
            "message": f"Patient {created['first_name']} {created['last_name']} registered successfully."
        }
    except Exception as e:
        logger.error(f"Error registering patient via Retell: {e}")
        return {"success": False, "error": str(e), "message": f"Registration failed: {str(e)}"}


@app.post("/update-patient", include_in_schema=False)
async def update_patient_tool(request: Request):
    """Retell AI Tool: Updates an existing patient record."""
    body = await request.json()
    args = body.get("args", body) if isinstance(body.get("args"), dict) else body
    phone = clean_phone(args.get("phone_number"))
    if not phone:
        return {"success": False, "message": "Phone number is required to locate your record."}

    # Locate patient by phone
    p = supabase.table("patients").select("*").eq("phone_number", phone).is_("deleted_at", "null").limit(1).execute()
    if not p.data:
        return {"success": False, "message": f"No active record found for phone number {phone}."}

    patient_id = p.data[0]["patient_id"]
    update_data = {k: v for k, v in args.items() if k not in ("phone_number", "patient_id") and v is not None}
    if not update_data:
        return {"success": True, "message": "No new changes were provided to update."}

    try:
        validated = PatientUpdate(**update_data)
        updates = validated.model_dump(exclude_unset=True)
        if "date_of_birth" in updates and updates["date_of_birth"]:
            updates["date_of_birth"] = str(updates["date_of_birth"])
        if "sex" in updates and hasattr(updates["sex"], "value"):
            updates["sex"] = updates["sex"].value
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        res = supabase.table("patients").update(updates).eq("patient_id", patient_id).execute()
        updated_row = res.data[0]
        return {
            "success": True,
            "patient_id": patient_id,
            "first_name": updated_row["first_name"],
            "last_name": updated_row["last_name"],
            "message": f"Successfully updated information for {updated_row['first_name']} {updated_row['last_name']}."
        }
    except Exception as e:
        logger.error(f"Error updating patient via Retell: {e}")
        return {"success": False, "error": str(e), "message": f"Update failed: {str(e)}"}


@app.post("/webhook/retell", include_in_schema=False)
@app.post("/webhook", include_in_schema=False)
async def retell_webhook(request: Request):
    """
    Retell AI Post-Call Webhook:
    Triggered when a call ends ('call_ended' or 'call_analyzed').
    Extracts transcript and audio recording, links them to the caller's 
    record in 'patients', and logs the event in 'call_logs'.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}

    event = body.get("event")
    call = body.get("call", {})
    logger.info(f"Retell Webhook received event: {event}")

    call_obj = call if isinstance(call, dict) and call else body
    transcript = call_obj.get("transcript")
    recording_url = call_obj.get("recording_url")
    duration_ms = call_obj.get("duration_ms") or 0
    duration_sec = duration_ms // 1000 if isinstance(duration_ms, int) else None
    retell_call_id = call_obj.get("call_id")

    # Extract caller phone number
    raw_phone = (
        call_obj.get("from_number")
        or call_obj.get("customer", {}).get("number")
        or call_obj.get("user_phone")
    )
    phone = None
    if raw_phone:
        try:
            phone = clean_phone(raw_phone)
        except Exception:
            phone = raw_phone

    patient_id = None
    if phone:
        # Match patient by phone number
        p = supabase.table("patients").select("patient_id, first_name, last_name").eq("phone_number", phone).is_("deleted_at", "null").limit(1).execute()
        if p.data:
            patient_id = p.data[0]["patient_id"]
            update_data = {}
            if transcript:
                update_data["last_call_transcript"] = transcript
            if recording_url:
                update_data["last_call_recording_url"] = recording_url
            if update_data:
                supabase.table("patients").update(update_data).eq("patient_id", patient_id).execute()
                logger.info(f"Updated patient {patient_id} with transcript.")

    # Also log to call_logs table
    try:
        supabase.table("call_logs").insert({
            "patient_id": patient_id,
            "vapi_call_id": retell_call_id,
            "caller_phone": phone or "Unknown",
            "call_status": "completed",
            "call_duration_seconds": duration_sec,
            "transcript": transcript,
            "recording_url": recording_url
        }).execute()
    except Exception as e:
        logger.warning(f"Could not insert call_logs record: {e}")

    return {"status": "success", "event": event, "patient_id": patient_id}


# =============================================================================
# 6. STATIC DASHBOARD ROUTE
# =============================================================================

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

