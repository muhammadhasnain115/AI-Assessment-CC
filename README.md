# Voice AI Agent — Patient Registration System

A lightweight, production-ready Voice AI patient demographic intake system accessible via telephone. The system conducts natural conversations to register patients, validates data strictly server-side, persists records to a managed **Supabase PostgreSQL** database, and exposes an API and web dashboard.

---

## 📁 Clean & Minimal Codebase Structure

The entire project is structured to be self-contained and easy to explain:

```
├── main.py                 # Core FastAPI service (API, Pydantic validation, routes, Vapi/Retell webhook)
├── static/
│   └── index.html          # Self-contained Web Dashboard (HTML + CSS + JS in a single file)
├── schema.sql              # PostgreSQL schema with constraints, indexes, triggers & seed data
├── voice_agent_prompt.md   # Voice AI system prompt, persona rules & tool schemas
├── test_api.py             # Automated test suite verifying all endpoints & validation rules
├── requirements.txt        # Minimal Python dependencies
└── .env                    # Supabase credentials & server configuration
```

---

## 🌟 Live Demo & Credentials for Reviewers

| Component | URL / Details | Notes |
| :--- | :--- | :--- |
| **Live Phone Number** | *Provided in submission email* | Real dialable U.S. number provisioned for reviewer evaluation (kept private from public repo to protect live call credits) |
| **API Base URL** | `https://ai-assessment-cc.onrender.com` | Standard `{ "data": ..., "error": null }` envelope |
| **Interactive Docs** | `https://ai-assessment-cc.onrender.com/docs` (Swagger UI) | Test endpoints directly in browser |
| **Reviewer Dashboard** | `https://ai-assessment-cc.onrender.com/dashboard` | Clean clinical UI with name search, server-side pagination & patient details |
| **Seed Test Records** | Jane Doe (`3055550199`) & Carlos Hernandez (`2125550144`) | Call or query using these numbers to test duplicate detection & updates |

---

## 🚀 API Endpoints Overview

| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | System health check (used by UptimeRobot keep-alive) | `200` |
| `GET` | `/patients` | List active patients. Supports `?search=`, `?page=`, `?limit=10`, `?last_name=` | `200` |
| `GET` | `/patients/{id}` | Get single active patient by UUID | `200`, `404` |
| `POST` | `/patients` | Create new patient (validates name, non-future DOB, min 8-year age, 10-digit phone, state, ZIP) | `201`, `422` |
| `PUT` | `/patients/{id}` | Update existing patient (partial update allowed) | `200`, `404`, `422` |
| `DELETE` | `/patients/{id}` | Soft-delete patient (sets `deleted_at` timestamp; does not hard-delete) | `200`, `404` |
| `POST` | `/check-patient` | Voice AI tool: Check if caller already exists by phone number | `200` |
| `POST` | `/register-patient` | Voice AI tool: Validates and saves new patient from voice call | `200` |
| `POST` | `/update-patient` | Voice AI tool: Updates an existing patient's details from voice call | `200` |
| `GET` | `/dashboard` | Reviewer management web portal | `200` |

---

## 🎙️ Voice AI Flow & Prompt Engineering

Configured in [`voice_agent_prompt.md`](./voice_agent_prompt.md):
1. **Returning Caller Greeting:** Checks phone number on call start. If caller exists: *"It looks like we already have a record for [Name]. Would you like to update your information instead?"*
2. **Natural Demographic Intake:** Asks for required fields naturally. Handles spelling corrections letter-by-letter (*"Actually my last name is spelled D-A-V-I-S"*).
3. **Validation Re-prompting:** Re-prompts specifically if caller says an invalid date of birth, age less than 8 years, or 7-digit phone number.
4. **Smart Opt-in for Optional Fields:** Does not ask every optional field one by one. Asks required fields first, then asks: *"I can also collect your insurance information, emergency contact, and preferred language. Would you like to provide any of those today?"*
5. **Confirmation Read-back:** Reads all collected details back before saving to the database.
6. **Graceful Error Handling:** Informs caller politely if saving fails; never hangs up with silence.

---

## 💻 How to Run Locally

```bash
# 1. Activate environment
.\.venv\Scripts\Activate.ps1

# 2. Run automated tests
python -m pytest test_api.py -v

# 3. Start server & dashboard
uvicorn main:app --reload --port 8000
```

- Reviewer Dashboard: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🚢 Deployment (Render / Railway)

1. **Repository:**
   ```bash
   git clone https://github.com/muhammadhasnain115/AI-Assessment-CC.git
   cd AI-Assessment-CC
   ```
2. **Deploy on Render / Railway:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment Variables:
     - `SUPABASE_URL`: Your Supabase URL
     - `SUPABASE_KEY`: Your Supabase Key
