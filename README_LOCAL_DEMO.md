# [Nombre en Construcción] Local Prototype Demo

Welcome to the [Nombre en Construcción] prototype. This guide provides a straightforward, one-command setup to get the application running locally so you can present the core clinical workflow to doctors.

## Prerequisites

- [Docker](https://www.docker.com/) installed and running
- [Python 3.12](https://www.python.org/downloads/)
- [Node.js 20](https://nodejs.org/)

## One-Command Local Setup

Open your terminal in the project root (`expedienteMedico`) and run the bootstrap script:

```bash
# 1. Run the unified bootstrap script
./scripts/dev_bootstrap.sh

# 2. Start the backend server (runs on http://localhost:8000)
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

In a **second terminal**, start the frontend application:

```bash
cd frontend
npm ci
npm run dev
```

## Demo Credentials

The `seed_demo_data.py` script automatically creates the following doctor account:

- **Email**: `dr.demo@medrecord.mx`
- **Password**: `DemoPassword123!`

## What to Show in the Demo

1. **Dashboard & Patient Management**: Log in to see the generated patients. Show how to create a new patient with their full clinical profile (address, phone, allergies).
2. **Drafting a Note**: Open a patient's Expediente and create a draft note. Show how it can be edited and saved iteratively.
3. **Signing & Compliance**: Click "Firmar y Bloquear". Explain that this triggers cryptographic hashing and locking, designed to support NOM-004-style immutability. Show the "Nota firmada y bloqueada" badge.
4. **Audit Trail**: Explain that every single view, creation, and update is logged in an append-only database table. Show the "Eventos recientes de bitácora" in the dashboard.

---

*Note: This local setup uses an ephemeral ECDSA key for signing and bypasses AWS services (Cognito, KMS, WAF) to make the demo easy to run on any machine without cloud credentials.*
