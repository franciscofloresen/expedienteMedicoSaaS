# 🏥 CloudMedRecord SaaS — Expediente Clínico Electrónico

SaaS lean y minimalista de expediente clínico para médicos independientes en México. Cumple con la NOM-004-SSA3-2012.

> **Filosofía del proyecto:** "Construye lo mínimo que funcione". Nada de abstracciones no pedidas, nada de over-engineering.

## 🛠️ Stack Tecnológico

- **Frontend:** React 18 + Vite + TypeScript (CloudFront / S3).
- **Backend:** FastAPI + Python 3.12 (AWS Lambda vía Mangum).
- **Autenticación:** Clerk (Validación JWT directa en middleware).
- **Base de Datos:** PostgreSQL (AWS RDS `db.t4g.small` — no serverless) con SQLAlchemy y AsyncPG.
- **Auditoría:** AWS CloudWatch (Logs estructurados JSON vía `AuditMiddleware` para evitar saturar la BD).

## 🚀 Cómo levantar el proyecto localmente

### 1. Base de datos y Variables
Crea el archivo `backend/.env` con tus credenciales apuntando a RDS y a Clerk:
```env
DATABASE_URL=postgresql+asyncpg://<usuario>:<password>@<tu-rds-endpoint>/medrecord
CLERK_SECRET_KEY=sk_test_...
CLERK_ISSUER_URL=https://<tu-clerk-domain>
CORS_ORIGINS=["http://localhost:5173"]
ENVIRONMENT=development
```

### 2. Levantar el Backend

Abre una terminal:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
El API estará en `http://localhost:8000`.

### 3. Levantar el Frontend

Abre otra terminal:
```bash
cd frontend
npm install
npm run dev
```
La UI estará en `http://localhost:5173`.

## 📜 Estructura del Repositorio (Lo esencial)

- `frontend/`: UI moderna (Glassmorphism con CSS puro, sin Tailwind inflado). Uso intensivo de componentes funcionales y TanStack Query.
- `backend/app/`: API Rest asíncrona. Middlewares clave:
  - `TenantMiddleware`: Extrae info del usuario (como `user_email`) desde el JWT de Clerk.
  - `AuditMiddleware`: Registra cada petición (quién, qué, cuándo, IP) en JSON para que CloudWatch lo absorba.
- `scripts/`:
  - `audit.sh`: Pesca logs de CloudWatch de un doctor específico en milisegundos (`./scripts/audit.sh correo@ejemplo.com 1h`).
  - `backend/scripts/upgrade_tenant.py`: Asciende a un doctor a plan "Pro" (BD + Clerk).
- `terraform/`: Infraestructura como código real (API Gateway, Lambda, RDS).

## 💡 Diseño "Lazy Senior Dev" (YAGNI)

- **Cero Panel de Administración Web:** Administrar planes de médicos o auditar logs se hace directo desde scripts de terminal rápidos y eficientes. No necesitamos mantener UI de administrador.
- **Auditoría sin Tablas:** Guardar cada clic en PostgreSQL es caro y lento. Lo mandamos como un simple print de JSON a la salida estándar, AWS lo manda a CloudWatch y usamos `grep` con el shell script.
- **Cero frameworks pesados de CSS:** CSS puro (`index.css`) para hacer componentes de cristal (`glassmorphism`) nativos, limpios y rapidísimos.