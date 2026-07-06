# CloudMedRecord — Roadmap Beta v1

> **Filosofía:** El médico debe poder abandonar el papel el mismo día que se registra.
> Solo se construye lo que bloquea ese objetivo. Nada más.

---

## Stack de referencia

| Capa | Tecnología | Notas |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | CloudFront / S3 |
| Backend | FastAPI + Python 3.12 | AWS Lambda vía Mangum |
| Auth | Clerk | JWT validado en `TenantMiddleware` |
| Base de datos | PostgreSQL · RDS `db.t4g.small` | SQLAlchemy + AsyncPG |
| Auditoría | CloudWatch | JSON estructurado vía `AuditMiddleware` — sin tablas en BD |
| Infraestructura | Terraform | API Gateway + Lambda + RDS |
| Estilos | CSS puro | Glassmorphism nativo — sin Tailwind |

---

## Prioridad 1 — Expediente Clínico + Historia Clínica

**Objetivo:** Crear y mantener el expediente de un paciente cumpliendo NOM-004.

### Entidades

```
Patient
├── id (UUID)
├── tenant_id                           ← RLS lo aísla por médico automáticamente
├── expediente_number                   ← autoincremental por tenant
├── first_name
├── last_name
├── birth_date
├── sex
├── curp (nullable)
├── phone
├── email
├── address                             ← cifrar con encrypt_field() antes de guardar
├── emergency_contact
├── emergency_phone
├── blood_type
├── allergies
├── active (default True)               ← soft-delete visual, nunca borrar físicamente
├── created_at
└── updated_at

MedicalHistory
├── patient_id (FK → Patient)
├── hereditary_history
├── pathological_history
├── non_pathological_history
├── gynecological_history (nullable)
├── current_illness
├── interrogation_by_systems
├── observations
└── updated_at                          ← actualizable, no es inmutable
```

### Backend (FastAPI + AsyncPG)

```
POST   /api/v1/patients               → Crear paciente
GET    /api/v1/patients               → Listar pacientes del tenant
GET    /api/v1/patients/{id}          → Detalle paciente
PUT    /api/v1/patients/{id}          → Actualizar paciente

POST   /api/v1/patients/{id}/history  → Crear historia clínica
PUT    /api/v1/patients/{id}/history  → Actualizar historia clínica
GET    /api/v1/patients/{id}/history  → Obtener historia clínica
```

> Todos los endpoints protegidos por `TenantMiddleware` — el `tenant_id` viene del JWT de Clerk, nunca del body del request.

### Frontend — Vista Paciente

```
┌─────────────────────────────────────────┐
│  Juan Pérez Gómez · 42 años · H        │
│  Exp. #0042                             │
├─────────────────────────────────────────┤
│  [Resumen]  [Consultas]  [Historia]     │
└─────────────────────────────────────────┘
```

- Estado del servidor: TanStack Query — no Redux, no estado global manual
- Glassmorphism en tarjetas de paciente con CSS Variables nativas

### Reglas NOM-004
- `address` se cifra con `encrypt_field()` (KMS directo) antes de persistir
- `active = False` oculta de la UI pero el registro permanece intocable en BD
- La historia clínica es editable — la inmutabilidad aplica solo a consultas firmadas

---

## Prioridad 2 — Consulta / Encuentro

**Objetivo:** Registrar la consulta diaria completa con signos vitales, diagnóstico y plan.

### Entidad

```
Encounter
├── id (UUID)
├── patient_id (FK → Patient)
├── tenant_id
├── consultation_date
├── vital_signs (JSONB)                 ← flexible para beta; evita columnas sueltas
│   {                                      que habrá que migrar cuando lleguen
│     weight, height, temperature,         especialidades con campos distintos
│     blood_pressure, heart_rate,
│     respiratory_rate, oxygen_saturation
│   }
├── reason_for_visit
├── physical_exam
├── diagnosis                           ← texto libre; código CIE-10 se agrega en P5
├── diagnosis_code (nullable)           ← "J06.9" — se llena desde autocomplete CIE-10
├── treatment_plan
├── notes
├── signed (bool, default False)
├── signed_at (nullable)
├── status (draft | signed)
├── created_at
└── updated_at
```

### Backend

```
POST   /api/v1/encounters                   → Crear consulta (status: draft)
GET    /api/v1/encounters/{id}              → Detalle consulta
GET    /api/v1/patients/{id}/encounters     → Timeline del paciente
PUT    /api/v1/encounters/{id}              → Editar (solo si status = draft)
POST   /api/v1/encounters/{id}/sign         → Firmar y sellar (implementado en P3)
```

### Frontend — Formulario de consulta

```
┌─────────────────────────────────────────┐
│  Nueva Consulta · Juan Pérez            │
├─────────────────────────────────────────┤
│  Signos vitales                         │
│  Peso ___  Talla ___  T° ___  TA ___   │
├─────────────────────────────────────────┤
│  Motivo de consulta                     │
│  _______________________________________ │
│  Exploración física                     │
│  _______________________________________ │
│  Diagnóstico (buscar CIE-10)            │
│  _______________________________________ │
│  Plan de tratamiento                    │
│  _______________________________________ │
├─────────────────────────────────────────┤
│  [Guardar borrador]    [Firmar nota →]  │
└─────────────────────────────────────────┘
```

### Reglas NOM-004
- Solo se puede editar una consulta con `status = draft`
- Una consulta firmada: el trigger PostgreSQL lanza excepción en cualquier UPDATE/DELETE
- Correcciones post-firma → nueva consulta con referencia a la original (adenda)

---

## Prioridad 3 — Firma Electrónica

**Objetivo:** Conectar el frontend al endpoint `/sign` ya implementado en el backend.

> ⚠️ **El backend ya existe y está completo** (`firma.py`, `kms:Sign`, `canonical_serialize`).
> Esta prioridad es trabajo de frontend únicamente.

### Flujo completo

```
Médico pulsa "Firmar nota"
        ↓
Modal de confirmación:
"Esta nota quedará sellada permanentemente.
 No podrá modificarse. ¿Confirmar?"
        ↓
POST /api/v1/encounters/{id}/sign
        ↓
Backend (ya implementado):
  1. Consulta tabla tenants → nombre, cédula, especialidad real (no request.state)
  2. canonical_serialize(contenido + metadata del médico)
  3. kms:Sign → firma ECDSA P-256 via AWS KMS
  4. Guarda EncounterSignature en BD
  5. encounter.signed = True, signed_at = now(), status = "signed"
        ↓
Frontend:
  - TanStack Query invalida cache del encounter
  - Bloquea todos los campos del formulario
  - Muestra badge de firma
  - Habilita botón "Generar receta"
```

### Entidad (ya existe)

```
EncounterSignature
├── encounter_id
├── sha256
├── kms_signature
└── signed_at
```

### UI — Badge de nota firmada

```
┌─────────────────────────────────────────┐
│  ✓ Nota firmada                         │
│  27 Jun 2026 · 10:34 am                 │
│  Dr. [Nombre] · Cédula [número]         │
│  Firma verificable criptográficamente   │
└─────────────────────────────────────────┘
```

---

## Prioridad 4 — Receta Electrónica

**Objetivo:** Generar una receta imprimible en menos de 30 segundos.

> ⚠️ **La receta se genera en el frontend con `window.print()`.**
> No hay PDF en el backend. No hay `reportlab`. No hay S3 para esto.
> El `AuditMiddleware` registra el evento en CloudWatch automáticamente.

### Entidades

```
Prescription
├── id (UUID)
├── encounter_id (FK → Encounter)
├── tenant_id
├── indications (nullable)
├── recommendations (nullable)
└── created_at

PrescriptionMedication
├── id
├── prescription_id
├── medication_name
├── dosage
├── frequency
├── duration
└── instructions (nullable)
```

### Backend

```
POST   /api/v1/prescriptions                    → Crear receta
GET    /api/v1/prescriptions/{id}               → Obtener receta
GET    /api/v1/encounters/{id}/prescription     → Receta de una consulta
```

### Frontend — Formulario

```
┌─────────────────────────────────────────┐
│  + Agregar medicamento                  │
├─────────────────────────────────────────┤
│  Medicamento:  [Paracetamol         ]   │
│  Dosis:        [500 mg              ]   │
│  Frecuencia:   [cada 8 horas        ]   │
│  Duración:     [5 días              ]   │
│  Indicaciones: [Tomar con alimentos ]   │
├─────────────────────────────────────────┤
│  [+ Agregar otro]   [🖨 Imprimir receta] │
└─────────────────────────────────────────┘
```

### Layout `@media print`

```
┌─────────────────────────────────────────┐
│  Dr. [Nombre Completo]                  │
│  [Especialidad] · Cédula [número]       │
│  [Dirección consultorio] · [Teléfono]   │
│  ─────────────────────────────────────  │
│  Paciente: Juan Pérez Gómez · 42 años  │
│  Fecha: 27 de junio de 2026             │
│  ─────────────────────────────────────  │
│  Rx                                     │
│                                         │
│  1. Paracetamol 500 mg                  │
│     Tomar 1 tableta cada 8 hrs × 5 días │
│     Con alimentos.                      │
│                                         │
│  Indicaciones generales:                │
│  Reposo relativo, hidratación.          │
│  ─────────────────────────────────────  │
│  _______________________                │
│  Dr. [Nombre] · Cédula [número]         │
└─────────────────────────────────────────┘
```

### CSS de impresión
```css
@media print {
  .sidebar, .navbar, .buttons, .breadcrumb { display: none !important; }
  .prescription-print { display: block; }
  body { background: white; }
}
```
- Orientación: Portrait, tamaño carta o A4
- El médico pulsa "Imprimir receta" → `window.print()` → guarda como PDF o imprime directo

---

## Prioridad 5 — CIE-10 (top 500)

**Objetivo:** Autocomplete de diagnósticos sin cargar 70,000 registros en beta.

> El CSV completo de CIE-10 (~70k registros) se agrega solo si los médicos lo piden.
> Para beta: los ~500 códigos más frecuentes en medicina general cubren el 80% de los casos.

### Entidad

```
ICD10
├── code         (ej. "J06.9")
├── description  (ej. "Infección aguda de las vías respiratorias superiores")
└── category     (ej. "respiratorio")  ← para filtrar por especialidad en el futuro
```

### Backend

```
GET /api/v1/icd10?q={query}   → Buscar por código o descripción (max 10 resultados)
```

- Búsqueda con `ILIKE` en PostgreSQL — sin Elasticsearch, sin dependencias extra
- Respuesta en < 50ms desde RDS `db.t4g.small` con índice en `code` y `description`

### Carga inicial

```bash
# Correr una sola vez después de las migraciones
PYTHONPATH=. python scripts/seed_icd10_top500.py
```

### Frontend — Autocomplete en campo Diagnóstico

```
Diagnóstico
┌─────────────────────────────────────────┐
│  infec resp...                          │
├─────────────────────────────────────────┤
│  J06   Infección aguda vías resp. sup.  │
│  J06.9 Infección aguda vías resp. NE    │ ← seleccionar
│  J00   Rinofaringitis aguda             │
└─────────────────────────────────────────┘
```

- Busca por código (`J06`) y por descripción (`infeccion resp`) con debounce 300ms
- Seleccionar guarda `diagnosis_code + diagnosis_description` en el Encounter
- El campo sigue siendo texto libre — el médico no está forzado a usar CIE-10

---

## Reglas globales — aplican a las 5 prioridades

| Regla | Dónde aplica | Cómo está implementado |
|---|---|---|
| `encrypt_field()` en datos sensibles | `address` en Patient | KMS directo en `encryption.py` |
| Inmutabilidad de registros firmados | Encounter firmado | Trigger PostgreSQL en migración Alembic |
| RLS por `tenant_id` | Todas las tablas | `SET LOCAL` en `session.py` |
| Auditoría de accesos | Todas las rutas | `AuditMiddleware` → CloudWatch JSON |
| Firma ECDSA en payload canónico | `POST /sign` | `firma.py` + KMS — no tocar |
| Retención mínima 5 años | Toda la BD | RDS backup + TODO S3 lifecycle 1825 días |
| No borrado real | Patient, Encounter, MedicalHistory | `active = False` / trigger |
| `tenant_id` siempre del JWT | Todos los endpoints | `TenantMiddleware` — nunca del body |

---

## Fuera del scope de beta

No construir hasta tener retroalimentación de médicos reales usando el sistema:

- Adjuntos clínicos (S3 presigned URLs)
- Agenda y calendario
- Plantillas clínicas por especialidad
- Dashboard con métricas
- Recordatorios WhatsApp / SMS
- Facturación CFDI
- Portal del paciente
- Teleconsulta
- CIE-10 completo (70k registros)
- IA clínica / transcripción de consulta
- Multi-sucursal
- App móvil nativa
- Integraciones HL7 / FHIR

---

## Scripts de administración disponibles

```bash
# Subir médico a plan Pro (BD + Clerk en una sola operación atómica)
PYTHONPATH=. python scripts/upgrade_tenant.py doctor@ejemplo.com

# Auditar acciones de un médico en CloudWatch
./scripts/audit.sh correo@ejemplo.com 1h
```
