#!/usr/bin/env bash
set -e

echo "=== MedRecord Local Prototype Bootstrap ==="

echo "[1/6] Starting local database..."
docker compose up -d

echo "[2/6] Setting up Python virtual environment..."
cd backend
if [ ! -d ".venv" ]; then
    python3.12 -m venv .venv
fi
source .venv/bin/activate
pip install -e ".[dev]"

echo "[3/6] Configuring local environment variables..."
if [ ! -f ".env.local" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env.local
    else
        echo "ENVIRONMENT=development" > .env.local
        echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord" >> .env.local
        echo "LOG_LEVEL=DEBUG" >> .env.local
    fi
fi

echo "[4/6] Running database migrations..."
alembic upgrade head

echo "[5/6] Seeding demo data..."
cd ..
python scripts/seed_demo_data.py

echo "=== Bootstrap Complete ==="
echo "You can now run the backend with:"
echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "And the frontend with:"
echo "  cd frontend && npm run dev"
