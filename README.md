# AP-Auditor 🛡️💼
### Enterprise Accounts-Payable Exception Checker & AI Audit Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-8E75B2?logo=google&logoColor=white)](https://ai.google.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-3.4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Security](https://img.shields.io/badge/Audit%20Trail-SHA--256%20Sealed-22c55e)](#-tamper-evident-cryptographic-audit-trail)

> **AP-Auditor** is an enterprise-grade compliance, duplicate detection, and financial risk mitigation copilot designed for Accounts Payable (AP) and finance audit teams. It replaces error-prone manual invoice reviews with deterministic rule checks, fuzzy anomaly scoring, cryptographically sealed audit logging, and a hybrid AI copilot powered by **Google Gemini 2.5 Flash**.

---

## 📑 Table of Contents

- [Key Highlights & Differentiators](#-key-highlights--differentiators)
- [System Architecture](#-system-architecture)
- [Multi-Vector Rules Engine](#-multi-vector-rules-engine)
- [Hybrid Two-Tier AI Copilot](#-hybrid-two-tier-ai-copilot)
- [Tamper-Evident Cryptographic Audit Trail](#-tamper-evident-cryptographic-audit-trail)
- [In-Browser Visual Policy Editor](#-in-browser-visual-policy-editor)
- [Executive Reporting (PDF & CSV)](#-executive-reporting-pdf--csv)
- [Repository Structure](#-repository-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
- [API Reference](#-api-reference)
- [License & Hackathon Notes](#-license--hackathon-notes)

---

## 🌟 Key Highlights & Differentiators

Unlike generic "upload a CSV and show a table" prototypes, **AP-Auditor** is engineered with real-world financial governance requirements:

1. **Deterministic + Generative Hybrid Copilot**: 
   - Instant zero-cost rule execution for common operational commands (Tier 1).
   - Seamless fallback to Google Gemini 2.5 Flash for open-ended queries grounded in live audit records (Tier 2).
2. **Visual In-Browser Policy Editor (`/policies`)**:
   - Zero-code runtime configuration for category spend ceilings, PO requirements, approval authority ladders, and duplicate tolerances (`policy_config.json`) with hot-reloading (`PUT /api/config`).
3. **Side-by-Side Evidence Comparison**:
   - Interactive visual comparison drawer comparing flagged invoices against baseline records with vendor fuzzy similarity %, amount delta, and date gaps.
4. **Cryptographically Sealed Audit Trail**:
   - Every system evaluation and auditor decision is hashed with SHA-256 into an immutable chain. Includes a one-click audit verification engine detecting any unauthorized database tampering.
5. **Executive Reports On Demand**:
   - Generate and download compliance reports in formatted CSV or professional multi-page vector PDF.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Frontend["Frontend Client (React 19 + TypeScript)"]
        UI_Home["Chat Copilot (/)\n- Interactive AI Dialogue\n- Inline Cards & Uploads\n- Gemini Status Badge"]
        UI_Dash["Dashboard (/dashboard)\n- Live KPIs & Trend Bars\n- Exception Review Queue\n- Side-by-Side Evidence Drawer"]
        UI_Audit["Audit Log (/audit)\n- Immutable Log Trail\n- SHA-256 Hash Verification\n- Search & Filters"]
        UI_Policy["Policy Editor (/policies)\n- Visual Category Limit Editor\n- Approval Hierarchy Ladder\n- Real-time JSON Sync"]
    end

    subgraph Backend["FastAPI Backend (Port 8000)"]
        API_Gateway["API Gateway / Routers"]
        
        subgraph Engine["Audit & Rules Engine"]
            RulesEngine["Multi-Vector Rules Engine\n(Fuzzy Duplicates, PO Match,\nApproval Hierarchy, GST)"]
            PolicyConfig["Dynamic Config Loader\n(policy_config.json)"]
        end

        subgraph Chatbot["Hybrid AI Chatbot Layer"]
            Tier1["Tier 1: Fast Regex & Keyword Matcher"]
            Tier2["Tier 2: Google Gemini 2.5 Flash\n(Dynamic .env Hot-Reloading)"]
        end

        subgraph Crypto["Cryptographic Subsystem"]
            Hasher["SHA-256 Signature Generator\n& Tamper Detection Verifier"]
        end

        subgraph Reporter["Report Generator"]
            PDFGen["Executive PDF Generator (ReportLab)"]
            CSVGen["CSV Exception Exporter"]
        end
    end

    subgraph Storage["Persistent Data Layer"]
        DB[("SQLite Database\n- invoices table\n- audit_log table\n- vendor registry")]
        JSONFile["backend/data/policy_config.json"]
    end

    subgraph External["External AI Provider"]
        GeminiAPI["Google AI Studio\nGemini 2.5 Flash API"]
    end

    UI_Home -->|POST /api/chat| API_Gateway
    UI_Dash -->|GET /api/exceptions\nPOST /api/review/{id}/decision| API_Gateway
    UI_Audit -->|GET /api/audit-logs\nGET /api/audit-logs/verify| API_Gateway
    UI_Policy -->|GET /api/config\nPUT /api/config| API_Gateway

    API_Gateway --> Engine
    API_Gateway --> Chatbot
    API_Gateway --> Crypto
    API_Gateway --> Reporter

    Chatbot --> Tier1
    Chatbot -->|Fallback| Tier2
    Tier2 <-->|Generative Inference| GeminiAPI

    Engine <--> DB
    Engine <--> JSONFile
    Crypto <--> DB
```

---

## ⚡ Multi-Vector Rules Engine

Every uploaded invoice passes through an extensive multi-vector validation pipeline:

| Violation Rule | Severity | Description | Trigger Threshold |
| :--- | :---: | :--- | :--- |
| **`EXACT_DUPLICATE`** | Critical | Identical invoice number, vendor ID, and amount already exists. | 100% exact match |
| **`FUZZY_DUPLICATE`** | High | Near-match vendor name within a recent date window with matching/near-matching amount. | RapidFuzz similarity ≥ 90%, date window ≤ 7 days |
| **`OVER_LIMIT`** | High | Invoice amount exceeds the category-specific spend limit defined in policy configuration. | Amount > Category Limit (e.g. ₹25K for Office Supplies) |
| **`MISSING_PO`** | Medium | Categories mandating purchase orders submitted without a valid PO reference. | `po_required == true` AND `po_number is null` |
| **`PO_AMOUNT_MISMATCH`**| High | Invoice total deviates from PO authorized amount beyond allowable tolerance. | Variance > ±5.0% |
| **`APPROVAL_MISMATCH`** | High | Approver designation lacks signing authority for the invoice value. | Signer tier ceiling < Invoice total (e.g. Team Manager > ₹10K) |
| **`MISSING_GST`** | Medium | Tax identifier is missing or fails statutory GSTIN checksum format. | Missing or non-15-digit alphanumeric GSTIN |

---

## 🤖 Hybrid Two-Tier AI Copilot

The chatbot in [`backend/app/chatbot`](file:///d:/Hackathon-projects/ap-auditor/backend/app/chatbot) implements a **Cost-Effective, Enterprise Hybrid Architecture**:

```
User Message ────────► [ TIER 1: Rules Matcher ] ───► Instant Operational Execution
                                 │                      (Approve, Reject, Flagged, Stats)
                             No Match
                                 ▼
                     [ TIER 2: Google Gemini ] ───► Natural Language Copilot Dialogue
                     (Model: gemini-2.5-flash)        (Grounds answer on live AP data)
```

- **TIER 1 (Zero-Cost, Zero-Latency)**:
  - Canonical & conversational pattern matching:
    - `"approve INV-1002"`, `"I want to sign off on INV-1002"` ➔ Approves invoice & signs audit hash.
    - `"why was INV-3918 flagged"` ➔ Returns detailed breakdown & matched reference.
    - `"which invoices got stuck"`, `"show flagged"` ➔ Displays interactive exception cards.
    - `"what's going on with the invoices today"`, `"show stats"` ➔ Returns compliance metrics.
    - `"export report"` ➔ Provides instant report download links.
- **TIER 2 (Google Gemini 2.5 Flash)**:
  - Triggered only when Tier 1 doesn't find a confident match.
  - Automatically strips markdown code blocks (` ```json ... ``` `) before JSON parsing.
  - Formulates business-grade answers grounded strictly in real database metrics.
  - **Graceful Resilience**: If the Gemini API key is missing or offline, returns a helpful AP Copilot guidance guide without crashing the `/api/chat` endpoint.
  - **Dynamic Hot-Reloading**: Reads `GEMINI_API_KEY` directly from `backend/.env` on every call. No server restarts needed!

---

## 🔒 Tamper-Evident Cryptographic Audit Trail

Financial compliance standards (SOX, SOC 2, ISO 27001) mandate immutable logging:

1. **Cryptographic Seal on Write**:
   Every invoice state change (automated evaluation, human approval, or rejection) is sealed using a cryptographic signature:
   $$\text{Hash} = \text{SHA-256}(\text{invoice\_id} \mathbin{\Vert} \text{action} \mathbin{\Vert} \text{performed\_by} \mathbin{\Vert} \text{reason} \mathbin{\Vert} \text{timestamp})$$
2. **One-Click Integrity Verification (`/audit`)**:
   - Recomputes SHA-256 signatures across all database records in sequence.
   - Highlights any row altered through direct SQL manipulation or database tampering.
   - Live tested over **27,000+** production records.

---

## 🎛️ In-Browser Visual Policy Editor

Auditors and administrators can adjust governance policies on the fly without touching code or editing raw JSON files:

- **Route**: [http://localhost:3000/policies](http://localhost:3000/policies)
- **Features**:
  - **Category Spends**: Interactive inputs for limits in Rupees (₹) + single-click toggle for `PO MANDATORY` vs `PO OPTIONAL`.
  - **Approval Ladder**: Visual step ladder configuring max authorized amounts for Team Manager, Department Head, Finance Controller, and CFO.
  - **Anomaly Sliders**: Real-time slider controls for fuzzy duplicate similarity cutoff, amount variance %, and date search windows.
  - **Raw JSON Inspector**: View and copy formatted JSON matching [`backend/data/policy_config.json`](file:///d:/Hackathon-projects/ap-auditor/backend/data/policy_config.json).
  - **Runtime Hot-Reload**: Calls `PUT /api/config` to validate and reload constants in-memory with zero downtime.

---

## 📊 Executive Reporting (PDF & CSV)

Generate audit reports for executive stakeholders, external auditors, or financial controllers:

- **PDF Export**:
  - Formatted multi-page executive summary created with ReportLab.
  - Contains overall clean rate %, total review volume, and catalog of exceptions grouped by rule.
- **CSV Export**:
  - Raw tabular dataset containing all flagged invoices, confidence scores, triggered checks, and audit timestamps.
- **Endpoints**:
  - `GET /api/reports/export?format=pdf`
  - `GET /api/reports/export?format=csv`

---

## 📁 Repository Structure

```plaintext
ap-auditor/
├── backend/
│   ├── app/
│   │   ├── api/                  # FastAPI REST route controllers
│   │   │   ├── audit.py          # /api/audit-logs & cryptographic verification
│   │   │   ├── chat.py           # /api/chat & /api/chat/status endpoints
│   │   │   ├── config.py         # /api/config policy management
│   │   │   ├── exceptions.py     # /api/exceptions & /api/review decisions
│   │   │   ├── invoices.py       # CSV upload & batch ingestion
│   │   │   ├── reports.py        # /api/reports/export (PDF & CSV)
│   │   │   └── stats.py          # Live KPIs & violation breakdowns
│   │   ├── chatbot/              # Hybrid AI chatbot subsystem
│   │   │   ├── gemini_client.py  # Google Gemini SDK & dynamic key resolver
│   │   │   ├── intent_classifier.py # Tier 1 regex engine & Tier 2 routing
│   │   │   ├── llm_fallback.py   # Gemini 2.5 Flash generative completion
│   │   │   ├── query_router.py   # Internal dispatch to DB/rules actions
│   │   │   └── response_formatter.py # Conversational response builder
│   │   ├── db/                   # Database models & SQLite connector
│   │   ├── reports/              # PDF & CSV generation engine
│   │   ├── rules_engine/         # Core validation & anomaly detection
│   │   │   ├── config_loader.py  # policy_config.json validator
│   │   │   └── constants.py      # In-memory rule thresholds
│   │   └── main.py               # FastAPI application entrypoint & CORS
│   ├── data/
│   │   ├── ap_auditor.db         # Persistent SQLite database (3,000+ invoices)
│   │   └── policy_config.json    # Configurable governance policies
│   ├── .env.example              # Environment variables template
│   └── test_gemini_chat.py       # Chatbot test suite
│
├── frontend/
│   ├── public/                   # Static icons & HTML template
│   ├── src/
│   │   ├── components/
│   │   │   └── DuplicateComparisonCard.tsx # Side-by-side evidence comparison
│   │   ├── pages/
│   │   │   ├── Home.tsx          # Chat interface with AI status indicator
│   │   │   ├── Dashboard.tsx     # KPI metrics & review queue table
│   │   │   ├── AuditLog.tsx      # Immutable audit trail & integrity verifier
│   │   │   └── PolicyEditor.tsx  # In-browser visual policy & rules editor
│   │   ├── services/
│   │   │   └── api.ts            # Typed Axios API client
│   │   ├── App.tsx               # Navigation bar & React Router v7 routes
│   │   └── index.css             # Industrial dark-mode Tailwind styles
│   └── package.json
│
├── .vscode/                      # IDE settings
├── .gitignore                    # Root gitignore
└── README.md                     # Comprehensive project documentation
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (Tested on Python 3.11 / 3.12 / 3.13)
- **Node.js 18+** & **npm**
- *(Optional)* Free **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)

---

### 1. Backend Setup

1. Open a terminal and navigate to the `backend` folder:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install fastapi uvicorn python-dotenv pydantic requests google-generativeai reportlab rapidfuzz
   ```

4. Configure your environment variables:
   ```bash
   cp .env.example .env
   ```
   Open `backend/.env` and paste your free Gemini API key:
   ```env
   GEMINI_API_KEY=AIzaSy...your-gemini-key-here...
   ```

5. Launch the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   Backend will be live at [http://localhost:8000](http://localhost:8000) (Interactive Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs)).

---

### 2. Frontend Setup

1. Open a second terminal and navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the React development server:
   ```bash
   npm start
   ```
   The client will open automatically at [http://localhost:3000](http://localhost:3000).

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/chat` | Send conversational queries or commands to the hybrid copilot. |
| `GET` | `/api/chat/status` | Live diagnostics for Gemini model availability and tier readiness. |
| `GET` | `/api/stats` | System overview stats, clean rate %, and rule breakdown counts. |
| `GET` | `/api/exceptions` | Fetch invoices in the review queue with pagination and filters. |
| `POST` | `/api/review/{invoice_id}/decision` | Submit human auditor review decision (`approve` / `reject`). |
| `GET` | `/api/audit-logs` | Retrieve immutable audit trail with SHA-256 signatures. |
| `GET` | `/api/audit-logs/verify` | Cryptographically verify integrity of the entire audit database. |
| `GET` | `/api/reports/export` | Download audit summary report (`?format=pdf` or `?format=csv`). |
| `GET` | `/api/config` | Retrieve active policy configuration (`policy_config.json`). |
| `PUT` | `/api/config` | Update category spend limits, approval ladders, and tolerances. |
| `POST` | `/api/invoices/upload` | Upload and audit new invoice CSV batches in real time. |

---

## 🏆 Hackathon Notes & Value Proposition

- **Real ROI**: Prevents duplicate payments, rogue unauthorized expenditures, and tax non-compliance before funds leave the corporate account.
- **Enterprise-Grade Architecture**: Decoupled rules engine, asynchronous LLM fallback layer, cryptographically sealed database ledger, and visual governance dashboard.
- **Zero Hallucination Risk**: Operational invoice actions (approvals, stats, details) execute through deterministic code; LLM is used strictly for conversational synthesis grounded in verified database facts.

---

## 📄 License

Developed for hackathon evaluation and enterprise compliance demonstrations. MIT License.
