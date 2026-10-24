C:\dev\autoagent-venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

Mahindra Virtual Assistant: multistage AI chat agent with Zoho CRM sync
Prototype of an end-to-end conversational agent for an automotive OEM. It recognises the customer's intent across the
purchase and ownership lifecycle and reads/writes Zoho CRM in real time.
Stage Customer says Agent does Zoho
1 New lead "XUV700 price? I'd like a test drive" answers from the local catalog, collects name, phone, email, city, confirms, creates the lead (dedupe by phone) Leads
2 Ongoing pipeline "Check my test drive" + phone or Deal ID verifies identity, reads the deal, updates the follow-up preference Deals
3 Booked vehicle "Where is my Scorpio-N?" + Booking ID or phone verifies identity, reports delivery stage, VIN, ETA, balance Deals (`Closed Won - Booking Done`)
4 Service "Brake noise, need a service" collects registration, odometer, issue, service center, confirms, creates a Case linked to the Contact Cases
Stack: Next.js 14 (App Router, TypeScript, Tailwind, SSE) · FastAPI · SQLAlchemy async + Alembic · PostgreSQL 16 ·
Groq `llama-3.3-70b-versatile` with Gemini fallback (direct SDK tool calling, no LangChain) · httpx.
Design details and diagrams: docs/architecture.md.

1. Prerequisites (Windows)
   Python 3.12, Node.js 20+
   PostgreSQL 16 installed locally (no Docker), service running, `psql` on PATH is helpful
   A Groq API key and/or a Gemini API key (free tiers work)
   For live CRM mode: a Zoho CRM developer account (section 3). For a no-credentials demo use `ZOHO_MODE=mock`.
2. Quick start

```powershell
# from the repo root
copy backend\.env.example backend\.env      # then edit: GROQ_API_KEY and/or GEMINI_API_KEY, DATABASE_URL password
.\scripts\dev.ps1 -Mock                      # offline demo: in-memory CRM pre-loaded with the seed data
```

`dev.ps1` checks prerequisites, creates `backend\.venv`, installs dependencies, creates the database if missing,
runs `alembic upgrade head`, starts the API on http://localhost:8000 and the UI on http://localhost:3000.
Flags: `-Seed` (seed live Zoho), `-SkipInstall`, `-NoStart`, `-Test` (run pytest), `-Stop`.
(If script execution is blocked: `Set-ExecutionPolicy -Scope Process Bypass`.)
Manual equivalent:

```powershell
cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
# second terminal
cd frontend; copy .env.example .env.local; npm install; npm run dev
```

.\.venv\Scripts\Activate.ps1
Health check: `GET http://localhost:8000/api/health` returns DB status, Zoho mode/token status, LLM key presence and retry-queue depth. 3. Live Zoho CRM setup
Sign up at https://www.zoho.com/crm/ (developer/free account). Note your data centre (India `.in`, US `.com`, EU `.eu`, AU `.com.au`).
Open the API Console (https://api-console.zoho.in or your region) → Self Client → note `client_id` / `client_secret`.
In the Self Client, Generate Code with scope `ZohoCRM.modules.ALL,ZohoCRM.settings.ALL`, time duration 10 minutes. Copy the code (starts `1000.`).
Exchange the code for a refresh token (code is single-use and expires in minutes):

```powershell
   Invoke-RestMethod -Method Post -Uri "https://accounts.zoho.in/oauth/v2/token" -Body @{
     grant_type="authorization_code"; client_id="<id>"; client_secret="<secret>"; code="<1000.code>" }
```

Save the `refresh_token` from the response (the refresh token does not expire; the service mints access tokens itself).
Fill `backend\.env`: `ZOHO_MODE=live`, `ZOHO_ACCOUNTS_URL`, `ZOHO_API_DOMAIN` (e.g. `https://www.zohoapis.in`), `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`.
Create the custom fields below (Setup → Customization → Modules and Fields). API names must match exactly.
`python scripts\seed_zoho.py --check-only` verifies fields and picklist values, then `python scripts\seed_zoho.py` seeds (idempotent).
Custom Zoho fields to create
Module API name Type Used for
Leads `Vehicle_Model` Single line model of interest (stage 1)
Leads `Chat_Session_ID` Single line trace back to the chat session
Deals `Vehicle_Model` Single line model on the deal
Deals `Variant` Single line e.g. AX7 Diesel AT, Z8L
Deals `Test_Drive_DateTime` Date/Time confirmed test drive
Deals `Quotation_Amount` Currency quoted amount (INR)
Deals `Quotation_Ref` Single line quotation number
Deals `Dealer_Name`, `Dealer_Phone` Single line dealer contact
Deals `Follow_Up_Preference` Multi line written by the agent (stage 2)
Deals `Booking_ID` Single line e.g. MAH-9921
Deals `Delivery_Stage` Picklist Booking Confirmed, Allocation Pending, VIN Allocated, Dispatch Pending, In Transit, Delivered
Deals `VIN` Single line
Deals `Expected_Delivery_Date` Date
Deals `Balance_Amount` Currency
Deals `Payment_Link` URL balance payment link, shown only if present
Cases `Registration_Number` Single line
Cases `Odometer_KM` Number
Cases `Service_Center` Single line
Cases `Chat_Ref` Single line idempotency tag
Also: add Deals › Stage picklist values `Test Drive Scheduled` and `Closed Won - Booking Done`; make sure your Lead Source picklist contains
the value in `ZOHO_LEAD_SOURCE` (default `Web Research`); and make sure a Cases module exists (if not, create a custom module
named `Cases` or set `ZOHO_CASES_MODULE`). The Case fields used by the mapper (`Subject`, `Related_To` Contact lookup, `Status`, `Priority`, `Case_Origin`,
`Description`) are in `backend/app/crm/mapper.py::case_to_zoho`: adjust there if your layout differs.
Seed data
Record Details Try it in chat
Lead Rajesh Sharma, Pune, Thar, `+91 98100 55001` new-lead dedupe: give this phone
Deal Priya Patel, XUV700 test drive in 3 days, `+91 98200 11002` phone + name `Priya Patel`
Booking `MAH-9921`, Scorpio-N Z8L, contact Anita Desai `+91 98330 22003`, In Transit Booking ID + last 4 digits `2003`
`ZOHO_MODE=mock` loads the same data in memory on every start, so the demo works offline. 4. Configuration
All keys and model names come from env (`backend/.env.example`, `frontend/.env.example`). Main ones: `DATABASE_URL`, `ZOHO_MODE`,
`ZOHO_*`, `LLM_PRIMARY` (`groq` or `gemini`), `GROQ_API_KEY`, `GROQ_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `NEXT_PUBLIC_API_URL`.
Real `.env` files are git-ignored and never packaged. 5. Tests

```powershell
.\scripts\dev.ps1 -Test         # or: cd backend; .\.venv\Scripts\python -m pytest -q
```

50 tests, using SQLite by default (set `TEST_DATABASE_URL=postgresql+asyncpg://...` to run on Postgres; the DB is wiped).
They cover the four workflows end to end (scripted LLM tool calls against the mock CRM), identity verification and lockout, confirm-before-write
(including bypass attempts), context switching, prompt injection, OAuth token refresh (cache, expiry, concurrency, 401 retry),
live Zoho HTTP mapping, the Zoho-down path (retry, queue, honest tool result, replay exactly once, dead-letter), LLM fallback, SSE and health. 6. Suggested 5 to 7 minute demo (Loom)
Open Zoho CRM in a second window. Chat: "What are the XUV700 variants?" → answer comes from the catalog; open the Debug drawer to show the tool call.
"I'm interested in the Thar, test drive in Mumbai" → give name/phone/email → confirm → show the new Lead (with `Vehicle_Model`) in Zoho.
New chat: "Check my test drive" → agent asks for phone + name → verify as Priya → show deal info → "call me after 7 PM" → confirm → show `Follow_Up_Preference` changing in Zoho.
Mid-chat switch: "Where is my booking MAH-9921?" → last 4 digits `2003` → delivery stage (stage badge moves to Booked vehicle).
"I need a service" → registration, odometer, issue, center → confirm → show the Case linked to the Contact.
Show resilience (live mode): temporarily set `ZOHO_API_DOMAIN` to an unreachable host and restart the backend, create a lead → honest "queued" message → restore the setting and restart → the queued lead syncs within `QUEUE_POLL_S` seconds (`/api/health` → `retry_queue_depth` returns to 0). 7. Troubleshooting
Symptom Fix
`PostgreSQL is not reachable at localhost:5432` Start the service (Services → postgresql-x64-16); check port/credentials in `DATABASE_URL`
`password authentication failed` Fix the password in `DATABASE_URL` (format `postgresql+asyncpg://user:pass@localhost:5432/autoagent`; URL-encode special characters)
`/api/health` → `"zoho": "error: ZohoAuthError"` Wrong region URLs, expired/incorrect refresh token, or credentials missing. Re-run step 3 to 5
`invalid_code` from Zoho The grant code is single-use and short-lived; generate a new one
Seed fails with `INVALID_DATA` / `MANDATORY_NOT_FOUND` A custom field or picklist value is missing: run `seed_zoho.py --check-only`
Cases step fails Cases module missing or different field names: see mapper note above
Chat replies "I'm sorry, I could not complete that" No LLM key set or all providers failing: check `/api/health` → `llm`, and the backend console
Groq `tool_use_failed` in logs Known llama-3.3 quirk; the router retries once, then falls back to Gemini
UI shows "Could not reach the assistant" Backend not running or `NEXT_PUBLIC_API_URL` wrong; CORS origin must be in `CORS_ORIGINS`
`dev.ps1` cannot be run `Set-ExecutionPolicy -Scope Process Bypass`
Port 8000/3000 busy `.\scripts\dev.ps1 -Stop`, or stop the other process 8. Honest limitations
Live Zoho and live LLM calls were not exercised in the build environment (no credentials). The Zoho HTTP client is tested against mocked HTTP using Zoho's documented response shapes; the first run against your org may need field-name tweaks in `mapper.py`.
Verification is two-factor knowledge-based (no OTP). Fine for a prototype; use OTP for production.
Dead-letter queue items keep their payload for manual replay; purge policy is not implemented.
The vehicle catalog contains illustrative sample prices, not an official price list.
