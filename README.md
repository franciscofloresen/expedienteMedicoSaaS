# 🏥 MedRecord SaaS — Expediente Clínico Electrónico para México

> **SaaS de expediente clínico para médicos independientes privados. Cumplimiento total NOM-004-SSA3-2012 y NOM-024-SSA3-2012. LFPDPPP. Infraestructura AWS con Terraform. Well-Architected Framework.**

[![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?logo=amazon-aws)](https://aws.amazon.com)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform)](https://terraform.io)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![NOM-004](https://img.shields.io/badge/NOM--004--SSA3-2012-green)](https://dof.gob.mx)
[![NOM-024](https://img.shields.io/badge/NOM--024--SSA3-2012-green)](https://dof.gob.mx)

---

## 📊 Contexto de Mercado (Por qué este proyecto existe)

### El problema

El Decreto de Digitalización de Salud entró en vigor el **15 de enero de 2026**. Desde esa fecha, todos los prestadores de servicios de salud privados en México —incluyendo consultorios independientes— están obligados a llevar el expediente clínico en formato electrónico, cumpliendo la NOM-004 y NOM-024.

**El estado actual del mercado:**

| Segmento | Cifra | Fuente |
|---|---|---|
| Médicos en sector privado | ~98,571 | INEGI ESEP 2024 |
| Establecimientos privados | 2,747 | INEGI ESEP 2024 |
| Consultorios privados | 17,390 | INEGI ESEP 2024 |
| Sin sistema digital aún | ~40% | SaludTotal / Decreto 2026 |
| Mercado global ECE 2032 | $43.62B USD | Research proyecciones |
| Gasto salud privado MX 2025 | $1.7 billones MXN | Líder Empresarial |

### El hueco competitivo

Los competidores actuales tienen problemas claros que esta solución resuelve:

| Competidor | Precio/mes | Problema |
|---|---|---|
| **Nimbo** (Ecaresoft) | $499 MXN/usuario | NOM-024 parcial, caro para médico solo |
| **Medilink** | $450 + implementación | Orientado a clínicas grandes, curva de aprendizaje alta |
| **Luna Salud** | $350 / 3 usuarios | NOM-024 incompleto (cifrado y firma no auditables) |
| **Mi-Consultorio** | $299 | NOM-024 básico, sin audit trail real |
| **Medesk** | Variable por módulo | Latinoamérica genérico, no cumple NOMs mexicanas completamente |
| **→ Esta plataforma** | **$299-499 MXN** | **Cumplimiento NOM total + precio justo + diseñado para 1 médico** |

---

## 🏗️ Arquitectura

### Stack tecnológico

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│              React 18 + Vite + TypeScript                    │
│           (S3 + CloudFront + WAF + Shield Standard)          │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS (TLS 1.3)
┌─────────────────────────▼───────────────────────────────────┐
│                    WAF v2 (4 reglas)                          │
│         OWASP Core · SQLi · Bad Inputs · Rate Limit          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   API GATEWAY (REST)                         │
│        Throttling · JWT authorizer (Cognito)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
┌──────────▼──┐  ┌────────▼──────┐  ┌──▼─────────────┐
│ Lambda API  │  │  Cognito Auth │  │  KMS            │
│ FastAPI     │  │  MFA + JWT    │  │  1 CMK (encrypt)│
│ Python 3.12 │  │  15min token  │  │  1 ECDSA (sign) │
│             │  │               │  │  + tenant DEKs  │
│ + tenacity  │  │  Password:    │  │                 │
│   (retries) │  │  12+ chars    │  │  $2.15/mes      │
└──────────┬──┘  └───────────────┘  └─────────────────┘
           │ (VPC privada)
┌──────────▼───────────────────────────────────────────┐
│            RDS Proxy (Connection Pool)                │
│         IAM auth · 100 max connections               │
└──────────┬───────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────┐
│       Aurora PostgreSQL Serverless v2 (15.4)         │
│     Min: 0.5 ACU ($43/mes) · Max: 4.0 ACU           │
│     Cifrado: KMS AES-256 (envelope encryption)      │
│     Multi-AZ: 2 zonas de disponibilidad              │
│     Backup: 35 días retención · PITR < 5 min        │
│     Row-Level Security: HABILITADO + FORZADO         │
│     Performance Insights: ON (gratis 7 días)         │
└──────────┬───────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────┐
│                S3 (3 buckets)                        │
│  ├── expedientes/     (Standard → IA → Glacier IR)   │
│  ├── audit-logs/      (Object Lock · WORM)           │
│  └── consentimientos/ (PDF + SHA-256 hash)           │
│                                                      │
│  Lifecycle: 0-90d Standard → 90-365d IA              │
│            → 365d+ Glacier IR → 1825d expirar        │
└──────────────────────────────────────────────────────┘

Observabilidad: CloudTrail + CloudWatch (Logs + 5 Alarmas)
               + Route53 Health Check + SNS + SQS DLQ
```

### Los 5 pilares Well-Architected aplicados

#### 1. 🔒 Seguridad (Pilar más crítico — NOMs lo exigen)

**Controles implementados:**
- **Cifrado en reposo:** Envelope encryption con AWS KMS. 1 CMK simétrica (AES-256, rotación anual automática) genera Data Encryption Keys (DEKs) únicos por tenant. Cada DEK se almacena cifrado en tabla `tenant_keys`. Limita el radio de explosión: comprometer un DEK solo expone datos de un tenant
- **Cifrado en tránsito:** TLS 1.3 forzado en CloudFront y API Gateway
- **Autenticación:** Cognito con MFA obligatorio + JWT de corta duración (15 min) + refresh token (7 días). Política de contraseña: mínimo 12 caracteres, mayúsculas + minúsculas + números + símbolos
- **Autorización:** IAM Roles + políticas de mínimo privilegio por función Lambda
- **Aislamiento de datos:** PostgreSQL Row-Level Security (RLS) habilitado y forzado en todas las tablas con `tenant_id`. El middleware extrae `tenant_id` del JWT y ejecuta `SET LOCAL "app.current_tenant"` por transacción. Doble barrera: middleware + RLS
- **Auditoría:** CloudTrail (todas las llamadas API de AWS) + tabla `audit_log` en BD (append-only, NUNCA se actualiza ni elimina). TODA acción sobre expedientes queda registrada (NOM-004 y NOM-024)
- **WAF:** 4 reglas: OWASP Core Rule Set, SQL Injection, Known Bad Inputs, Rate Limiting (1,000 req/5min por IP)
- **Red:** VPC dedicada, Lambda en subnets privadas, RDS inaccesible desde internet, RDS Proxy con IAM auth
- **Secretos:** AWS Secrets Manager con rotación automática cada 30 días. Cache en memoria Lambda con TTL de 5 minutos. NUNCA en variables de entorno plain text
- **Firma electrónica:** ECDSA P-256 vía AWS KMS (ver detalle abajo). Llave compartida con `EncryptionContext` por tenant. CloudTrail registra identidad del firmante (Cognito), IP y timestamp. Inmutable post-firma
- **S3 Audit Logs:** Object Lock (WORM) — los logs de auditoría son inmutables a nivel de almacenamiento

**Firma electrónica — Detalle técnico:**

```
Flujo de firma:
1. Serializar contenido de la nota a JSON canónico (llaves ordenadas)
2. SHA-256 del contenido canónico → firma_hash_contenido
3. kms:Sign(KeyId=alias/medrecord-signing, Message=hash,
           SigningAlgorithm=ECDSA_SHA_256,
           EncryptionContext={tenant_id, nota_id, timestamp})
4. En una sola transacción de BD:
   a. Guardar firma (BYTEA), hash, key ARN, algoritmo
   b. Guardar snapshot del médico (nombre, cédula, especialidad)
   c. SET es_editable = FALSE
   d. INSERT en audit_log
5. CloudTrail registra: quién (Cognito identity), cuándo, desde dónde

Flujo de verificación:
1. Recuperar nota + firma de BD
2. Recalcular SHA-256 del contenido almacenado
3. kms:Verify(KeyId, firma, hash) → TRUE/FALSE
4. Comparar hash recalculado con firma_hash_contenido almacenado
```

> **¿Por qué llave compartida y no por tenant?** Una llave ECDSA por tenant cuesta $1 USD/mes cada una. Con 500 médicos = $500/mes solo en llaves. La llave compartida con `EncryptionContext` proporciona la misma fuerza criptográfica. La no-repudiación se garantiza porque CloudTrail registra la identidad del usuario autenticado (Cognito MFA) que ejecutó `kms:Sign`. El campo `firma_kms_key_id` en BD permite migrar a llaves por tenant en el futuro sin cambiar el esquema.

#### 2. ⚡ Eficiencia de Rendimiento

- **Aurora Serverless v2:** Escala de 0.5 a 4 ACU automáticamente. No pagas por capacidad ociosa
- **Lambda sin Provisioned Concurrency:** Cold starts (~300ms) son aceptables para 50 médicos en horario laboral. Provisioned Concurrency ($38/mes) se activa solo cuando haya quejas reales de latencia
- **Connection pooling:** RDS Proxy para no saturar conexiones de BD con Lambdas concurrentes (máx 100 conexiones)
- **CloudFront:** CDN, assets del frontend cacheados al edge. TTFB < 100ms en México
- **Índices BD:** `expediente_id`, `tenant_id`, `paciente_curp`, `creado_en` indexados desde el inicio
- **Cache de secretos:** Secrets Manager cacheado en memoria Lambda (TTL 5 min) para evitar latencia de API calls
- **Cache de DEKs:** Data Encryption Keys cacheados en memoria Lambda (TTL 5 min) para evitar llamadas repetidas a KMS Decrypt
- **Retry patterns:** `tenacity` con exponential backoff para llamadas a KMS, S3, y RDS Proxy. Circuit breaker básico para evitar cascadas de fallos

#### 3. 💰 Optimización de Costos (SaaS lean = breakeven rápido)

**Costo real estimado para 50 médicos en producción:**

| Servicio | Configuración | USD/mes |
|---|---|---|
| Aurora Serverless v2 | 0.5-4.0 ACU, solo writer | ~$43 |
| RDS Proxy | 1 proxy | ~$21.60 |
| Lambda | ~1M invocaciones, 512MB | ~$2.80 |
| API Gateway | 1M requests | ~$3.50 |
| CloudFront | 50GB transfer | ~$4.25 |
| S3 (todos los buckets) | 30GB total | ~$0.80 |
| Cognito | <50K MAU | **Gratis** |
| KMS | 2 llaves + ~100K API calls | ~$2.30 |
| Secrets Manager | 2 secretos + rotación | ~$0.80 |
| WAF v2 | 1 ACL, 4 reglas, ~1M req | ~$10 |
| CloudTrail | Management + S3 data events | ~$2 |
| CloudWatch | Logs (5GB) + 5 alarmas | ~$3.50 |
| Route53 | 1 hosted zone + 1 health check | ~$2 |
| SES | 2K emails | ~$0.20 |
| SNS + SQS | Alertas + DLQ | ~$0.15 |
| Shield Standard | Incluido | **Gratis** |
| **TOTAL** | | **~$97 USD/mes** |

**Análisis de márgenes:**

| Escenario | Ingreso (MXN) | Ingreso (USD) | Infra (USD) | **Margen** |
|---|---|---|---|---|
| 10 médicos × $299 | $2,990 | ~$155 | $97 | **37%** |
| 10 médicos × $499 | $4,990 | ~$260 | $97 | **63%** |
| 30 médicos × $499 | $14,970 | ~$780 | $97 | **88%** |
| 50 médicos × $499 | $24,950 | ~$1,300 | $97 | **92%** |
| 100 médicos × $499 | $49,900 | ~$2,600 | ~$140 | **95%** |

> **Breakeven: ~7 médicos a $499 MXN/mes** o ~13 médicos a $299. Los costos de infraestructura son casi planos hasta 100+ médicos porque Aurora Serverless, Lambda y Cognito escalan desde casi cero.

**Estrategia S3 Lifecycle (NOM-004: conservar 5 años mínimo):**
```
Día 0-90:    S3 Standard     ($0.023/GB)
Día 90-365:  S3 Standard-IA  ($0.0125/GB) — 45% ahorro
Día 365+:    S3 Glacier IR   ($0.004/GB)  — 83% ahorro vs Standard
Día 1825:    Expirar (5 años = cumplimiento NOM)
```

#### 4. 🔧 Excelencia Operacional

- **IaC completo:** Todo en Terraform. Ningún recurso manual en consola AWS
- **GitHub Actions CI/CD:** Test → Build → Deploy a staging → Aprobación manual → Deploy prod
- **Ambientes:** `dev`, `staging`, `prod` con workspaces de Terraform
- **5 alarmas críticas:** (1) Lambda error rate > 5%, (2) API Gateway 5xx > 1%, (3) Aurora CPU > 80%, (4) API latencia p99 > 3s, (5) DLQ message count > 0
- **Alertas:** SNS → Email cuando se dispara cualquier alarma
- **Health check externo:** Route53 HTTPS health check desde 3 regiones (us-east-1, us-west-2, eu-west-1)
- **Runbooks:** Documentados en `/docs/runbooks/` para cada tipo de incidente
- **Security scanning:** Checkov en CI para validar configuración Terraform

#### 5. 🏗️ Confiabilidad

- **Multi-AZ:** Aurora Serverless v2 con réplica en segunda zona automáticamente
- **Backups:** Retención 35 días (máximo de Aurora), PITR con granularidad < 5 minutos
- **RPO < 5 minutos:** Aurora PITR lo soporta nativamente sin costo adicional
- **RTO < 1 hora:** Procedimiento de failover documentado en runbooks
- **Health checks:** Route53 HTTPS health check + alarmas CloudWatch automáticas
- **Dead Letter Queue:** SQS DLQ captura invocaciones Lambda fallidas (retención 14 días)
- **Retry patterns:** `tenacity` con exponential backoff en llamadas a servicios AWS. Circuit breaker básico para prevenir cascadas
- **Deletion protection:** Habilitada en Aurora y S3 (Object Lock en audit-logs)
- **Versionado S3:** Habilitado en todos los buckets para proteger contra eliminaciones accidentales

**Escalamiento futuro (triggers definidos):**

| Trigger | Acción | Impacto en costo |
|---|---|---|
| 50+ tenants | Agregar CloudWatch Dashboard | +$3/mes |
| 100+ tenants | Agregar replicación S3 cross-region para audit logs | +$5/mes |
| 100+ tenants | Agregar CloudWatch Synthetics canary | +$1.60/mes |
| 200+ tenants | Agregar WAF Bot Control | +$10/mes |
| 200+ tenants | Agregar WAF Geo-restriction | +$1/mes |
| 200+ tenants | Agregar Aurora read replica | +$43/mes |
| 300+ tenants | Subir Aurora min ACU a 1.0 | +$43/mes |
| 500+ tenants | Evaluar llaves ECDSA por tenant vs compartida | +$500/mes o CloudHSM |
| Quejas de latencia | Activar Lambda Provisioned Concurrency | +$38/mes |

---

## 📁 Estructura del Repositorio

```
medrecord-saas/
├── terraform/
│   ├── modules/
│   │   ├── networking/          # VPC, subnets, security groups, NAT
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── compute/             # Lambda functions, API Gateway, DLQ
│   │   ├── database/            # Aurora Serverless v2, RDS Proxy
│   │   ├── security/
│   │   │   ├── kms.tf           # 1 CMK (encrypt) + 1 ECDSA (sign)
│   │   │   ├── waf.tf           # 4 reglas: OWASP, SQLi, Bad Inputs, Rate Limit
│   │   │   ├── cloudtrail.tf
│   │   │   ├── iam.tf
│   │   │   └── secrets.tf       # Secrets Manager + rotación cada 30 días
│   │   ├── storage/             # S3 buckets + lifecycle + Object Lock
│   │   ├── auth/                # Cognito User Pool (MFA, password policy)
│   │   └── observability/       # CloudWatch (5 alarmas) + SNS + Route53 health
│   ├── environments/
│   │   ├── dev/
│   │   │   ├── main.tf
│   │   │   └── terraform.tfvars
│   │   ├── staging/
│   │   └── prod/
│   └── scripts/
│       ├── init.sh              # Bootstrap: S3 backend + DynamoDB lock
│       └── destroy-safe.sh      # Destruye todo EXCEPTO backups RDS
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── expedientes.py   # CRUD expedientes (NOM-004)
│   │   │   │   ├── notas.py         # Notas médicas + firma ECDSA
│   │   │   │   ├── pacientes.py     # Gestión de pacientes
│   │   │   │   ├── medicos.py       # Perfil médico + cédula
│   │   │   │   └── auth.py          # Endpoints de autenticación
│   │   ├── models/
│   │   │   ├── expediente.py    # SQLAlchemy models
│   │   │   ├── nota.py
│   │   │   ├── paciente.py
│   │   │   ├── audit.py         # Audit log model
│   │   │   └── tenant_key.py   # Envelope encryption DEK model
│   │   ├── services/
│   │   │   ├── encryption.py   # Envelope encryption (CMK + DEKs)
│   │   │   ├── firma.py        # Firma electrónica ECDSA P-256 vía KMS
│   │   │   ├── s3.py           # Upload/download archivos
│   │   │   └── notificaciones.py # SES emails + SNS
│   │   ├── middleware/
│   │   │   ├── audit.py         # Middleware: log TODA acción (NOM)
│   │   │   ├── tenant.py        # Multi-tenancy: JWT → SET LOCAL app.current_tenant
│   │   │   └── rate_limit.py    # Rate limiting por tenant
│   │   ├── db/
│   │   │   ├── session.py       # Async SQLAlchemy + SET LOCAL tenant context
│   │   │   ├── rls_init.sql     # Row-Level Security policies
│   │   │   └── migrations/      # Alembic migrations
│   │   └── core/
│   │       ├── config.py        # Settings + Secrets Manager cache (TTL 5 min)
│   │       ├── security.py      # JWT validation
│   │       ├── resilience.py    # Retry patterns (tenacity) + circuit breaker
│   │       └── nom_validator.py # Validaciones NOM-004 (campos obligatorios)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── nom_compliance/      # Tests específicos de cumplimiento normativo
│   │   └── security/            # Tests de RLS, firma, cifrado
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Expedientes/     # Lista y detalle
│   │   │   ├── NuevaConsulta/   # Formulario consulta (NOM-004)
│   │   │   ├── Pacientes/
│   │   │   └── Dashboard/
│   │   ├── components/
│   │   │   ├── FirmaElectronica/ # Componente de firma ECDSA
│   │   │   ├── NotaMedica/       # Editor de notas clínicas
│   │   │   ├── ConsentimientoInformado/
│   │   │   └── AvisoPrivacidad/ # Modal de aviso de privacidad (LFPDPPP)
│   │   ├── hooks/
│   │   ├── services/            # API calls
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
│
├── .github/
│   └── workflows/
│       ├── ci.yml               # Tests + checkov en cada PR
│       ├── deploy-staging.yml   # Auto-deploy a staging en merge a main
│       └── deploy-prod.yml      # Manual approval → prod
│
├── docs/
│   ├── nom-004-checklist.md     # Checklist completo de cumplimiento
│   ├── nom-024-checklist.md
│   ├── legal/
│   │   ├── aviso_privacidad_template.md  # Template LFPDPPP Art. 15-16
│   │   └── breach_protocol.md            # Protocolo de respuesta a brecha
│   ├── architecture-decisions/  # ADRs
│   └── runbooks/
│       ├── incident_response.md
│       └── secret_rotation.md
│
└── README.md                    # Este archivo
```

---

## 🗄️ Esquema de Base de Datos

### Modelo completo (NOM-004 al pie de la letra + LFPDPPP)

```sql
-- MULTI-TENANCY: cada médico es un tenant aislado
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_medico   VARCHAR(200) NOT NULL,
    cedula          VARCHAR(20) NOT NULL UNIQUE,
    especialidad    VARCHAR(100),
    rfc             VARCHAR(13),
    email           VARCHAR(200) UNIQUE NOT NULL,
    plan            VARCHAR(20) DEFAULT 'basico',  -- basico|profesional|clinica
    activo          BOOLEAN DEFAULT TRUE,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

-- LLAVES DE CIFRADO POR TENANT (envelope encryption)
CREATE TABLE tenant_keys (
    tenant_id       UUID PRIMARY KEY REFERENCES tenants(id),
    encrypted_dek   BYTEA NOT NULL,         -- DEK cifrado con CMK de KMS
    kms_key_id      VARCHAR(200) NOT NULL,  -- ARN del CMK que cifró este DEK
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    rotated_at      TIMESTAMPTZ             -- NULL hasta primera rotación
);

-- PACIENTES: datos de identificación NOM-004 §5.3
CREATE TABLE pacientes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    
    -- Campos obligatorios NOM-004
    nombre_completo     VARCHAR(200) NOT NULL,
    fecha_nacimiento    DATE NOT NULL,
    sexo                VARCHAR(10) NOT NULL CHECK (sexo IN ('M','F','X')),
    
    -- Campos opcionales pero recomendados
    curp                CHAR(18),
    entidad_nacimiento  VARCHAR(50),
    nacionalidad        VARCHAR(50) DEFAULT 'Mexicana',
    ocupacion           VARCHAR(100),
    
    -- Contacto
    telefono            VARCHAR(20),
    email               VARCHAR(200),
    
    -- Datos de seguro (si aplica)
    aseguradora         VARCHAR(100),
    num_poliza          VARCHAR(50),
    
    -- Dirección (cifrado con envelope encryption — dato sensible)
    domicilio_cifrado   BYTEA,
    
    -- Auditoría
    creado_por          UUID REFERENCES tenants(id),
    creado_en           TIMESTAMPTZ DEFAULT NOW(),
    modificado_en       TIMESTAMPTZ DEFAULT NOW(),
    
    -- Índices para búsqueda
    CONSTRAINT uq_paciente_tenant UNIQUE (tenant_id, curp)
);

-- EXPEDIENTES: entidad principal NOM-004
CREATE TABLE expedientes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    paciente_id         UUID NOT NULL REFERENCES pacientes(id),
    folio               VARCHAR(20) NOT NULL,  -- Folio interno consecutivo
    
    -- Historia clínica NOM-004 §5.4 al §5.7
    -- Cifrado con envelope encryption (datos altamente sensibles)
    antecedentes_cifrado BYTEA,   -- JSON: {heredo_familiares, personales_patologicos, etc}
    
    -- Estado del expediente
    estado              VARCHAR(20) DEFAULT 'activo',  -- activo|inactivo|archivado
    
    -- Auditoría
    creado_por          UUID NOT NULL REFERENCES tenants(id),
    creado_en           TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_folio_tenant UNIQUE (tenant_id, folio)
);

-- NOTAS MÉDICAS: núcleo clínico NOM-004 §5.8-§5.14
CREATE TABLE notas (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expediente_id       UUID NOT NULL REFERENCES expedientes(id),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    
    -- Tipo de nota (NOM-004 define tipos específicos)
    tipo_nota           VARCHAR(30) NOT NULL CHECK (tipo_nota IN (
                            'ingreso', 'evolucion', 'egreso', 
                            'interconsulta', 'referencia', 'traslado',
                            'quirurgica', 'anestesiologia', 
                            'enfermeria', 'urgencias', 'historia_clinica'
                        )),
    
    -- Contenido (NOM-004: fecha, hora, nombre y firma son obligatorios)
    contenido           TEXT NOT NULL,          -- Texto de la nota
    diagnostico_cie10   VARCHAR(10),            -- Código CIE-10 del diagnóstico
    
    -- Signos vitales (si aplica)
    signos_vitales      JSONB,  -- {pa, fc, fr, temp, sat_o2, peso, talla}
    
    -- Firma electrónica ECDSA P-256 vía KMS (INMUTABLE una vez firmada)
    firma_digital       BYTEA,                  -- Firma ECDSA P-256 (DER encoded)
    firma_hash_contenido VARCHAR(64),           -- SHA-256 del contenido canónico
    firma_kms_key_id    VARCHAR(200),           -- ARN de la llave KMS usada
    firma_algoritmo     VARCHAR(30) DEFAULT 'ECDSA_SHA_256',
    firmado_por         UUID REFERENCES tenants(id),
    firmado_en          TIMESTAMPTZ,
    es_editable         BOOLEAN DEFAULT TRUE,   -- FALSE después de firmar
    
    -- Datos del médico en el momento de firma (snapshot histórico)
    medico_nombre       VARCHAR(200),
    medico_cedula       VARCHAR(20),
    medico_especialidad VARCHAR(100),
    
    -- Auditoría
    creado_en           TIMESTAMPTZ DEFAULT NOW(),
    creado_por          UUID REFERENCES tenants(id)
);

-- CONSENTIMIENTOS INFORMADOS (NOM-004 §4.2)
CREATE TABLE consentimientos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    expediente_id   UUID NOT NULL REFERENCES expedientes(id),
    tipo            VARCHAR(50),      -- general|quirurgico|procedimiento_especifico
    s3_key          VARCHAR(500),     -- Ruta del PDF firmado en S3
    hash_documento  VARCHAR(64),      -- SHA-256 del PDF (integridad)
    firmado_por     VARCHAR(200),     -- Nombre del paciente o tutor
    firmado_en      TIMESTAMPTZ,
    creado_en       TIMESTAMPTZ DEFAULT NOW()
);

-- AVISOS DE PRIVACIDAD (LFPDPPP Art. 15-16)
CREATE TABLE avisos_privacidad (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    paciente_id     UUID NOT NULL REFERENCES pacientes(id),
    version_aviso   VARCHAR(10) NOT NULL DEFAULT '1.0',
    aceptado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consentimiento_datos_sensibles BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, paciente_id, version_aviso)
);

-- AUDIT LOG: OBLIGATORIO NOM-004 + NOM-024
-- Esta tabla NUNCA se actualiza, solo se inserta (append-only)
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,  -- Bigserial para trazabilidad cronológica
    tabla           VARCHAR(50) NOT NULL,
    registro_id     UUID NOT NULL,
    accion          VARCHAR(10) NOT NULL CHECK (accion IN ('SELECT','INSERT','UPDATE','DELETE')),
    tenant_id       UUID,
    usuario_id      UUID,
    ip_origen       INET,
    user_agent      TEXT,
    timestamp       TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    datos_antes     JSONB,      -- Estado anterior (para UPDATE)
    datos_despues   JSONB,      -- Estado nuevo
    exito           BOOLEAN DEFAULT TRUE,
    error_detalle   TEXT        -- Si exito=FALSE, razón del error
);

-- ============================================================
-- ROW-LEVEL SECURITY: aislamiento de datos por tenant
-- Defensa en profundidad — funciona incluso si el middleware falla
-- ============================================================

-- Habilitar y forzar RLS en todas las tablas con tenant_id
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pacientes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_pacientes ON pacientes
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE expedientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE expedientes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_expedientes ON expedientes
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE notas ENABLE ROW LEVEL SECURITY;
ALTER TABLE notas FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_notas ON notas
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE consentimientos ENABLE ROW LEVEL SECURITY;
ALTER TABLE consentimientos FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_consentimientos ON consentimientos
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

ALTER TABLE avisos_privacidad ENABLE ROW LEVEL SECURITY;
ALTER TABLE avisos_privacidad FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_avisos ON avisos_privacidad
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Audit log: cada tenant solo puede LEER sus propios logs,
-- pero INSERT es libre (el sistema necesita registrar acciones admin)
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_read_own ON audit_log
    FOR SELECT USING (tenant_id = current_setting('app.current_tenant')::uuid);
CREATE POLICY audit_write_all ON audit_log
    FOR INSERT WITH CHECK (true);

-- Rol de aplicación (NO superuser — los superusers bypasean RLS)
CREATE ROLE medrecord_app LOGIN;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medrecord_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO medrecord_app;
-- NO otorgar DELETE en tablas clínicas (cumplimiento NOM: sin eliminaciones)
REVOKE DELETE ON pacientes, expedientes, notas, consentimientos FROM medrecord_app;

-- ============================================================
-- ÍNDICES CRÍTICOS PARA RENDIMIENTO
-- ============================================================
CREATE INDEX idx_expedientes_tenant ON expedientes(tenant_id);
CREATE INDEX idx_expedientes_paciente ON expedientes(paciente_id);
CREATE INDEX idx_notas_expediente ON notas(expediente_id);
CREATE INDEX idx_notas_tipo ON notas(tipo_nota);
CREATE INDEX idx_audit_tenant_tiempo ON audit_log(tenant_id, timestamp DESC);
CREATE INDEX idx_pacientes_curp ON pacientes(curp) WHERE curp IS NOT NULL;
CREATE INDEX idx_avisos_paciente ON avisos_privacidad(tenant_id, paciente_id);
CREATE INDEX idx_consentimientos_expediente ON consentimientos(expediente_id);
```

---

## ⚖️ Cumplimiento Normativo

### NOM-004-SSA3-2012 — Checklist

| Requisito | Implementación | Estado |
|---|---|---|
| Datos de identificación del paciente | Tabla `pacientes` con campos obligatorios + validación en API | ✅ |
| Historia clínica completa (§5.4) | JSON cifrado con envelope encryption (KMS DEK) en `antecedentes_cifrado` | ✅ |
| Notas de evolución con fecha/hora/firma | Tabla `notas` + firma ECDSA P-256 + timestamp inmutable | ✅ |
| Consentimiento informado | Tabla `consentimientos` + PDF en S3 con hash SHA-256 | ✅ |
| Referencia y contrarreferencia | Tipo de nota `referencia` y `traslado` con datos destino | ✅ |
| Nota de egreso | Tipo de nota `egreso` con diagnóstico CIE-10 obligatorio | ✅ |
| Conservación mínima 5 años | S3 Lifecycle: Glacier IR año 1+ → Expirar día 1825 | ✅ |
| Responsabilidad del establecimiento | Multi-tenancy: cada médico es responsable de su tenant | ✅ |

### NOM-024-SSA3-2012 — Checklist

| Requisito | Implementación | Estado |
|---|---|---|
| Cifrado datos en reposo | Envelope encryption: KMS CMK AES-256 + DEKs por tenant | ✅ |
| Cifrado datos en tránsito | TLS 1.3 forzado en CloudFront + API Gateway | ✅ |
| Firma electrónica | ECDSA P-256 vía KMS + EncryptionContext por tenant. CloudTrail audita identidad del firmante | ✅ |
| Integridad de datos | SHA-256 en contenido de notas + consentimientos. Verificación con `kms:Verify` | ✅ |
| Control de acceso | Cognito MFA obligatorio + IAM mínimo privilegio + RLS en PostgreSQL | ✅ |
| Registro de auditoría | CloudTrail + tabla `audit_log` inmutable (append-only) + S3 Object Lock (WORM) | ✅ |
| Backup y recuperación | Aurora backup 35 días, PITR < 5 min. RPO < 5 min, RTO < 1 hora | ✅ |
| Disponibilidad | Multi-AZ Aurora + CloudFront CDN + Route53 health checks | ✅ |
| Identificación del sistema | Metadatos en cada nota: sistema, versión, timestamp | ✅ |

### LFPDPPP — Cumplimiento

| Requisito | Implementación | Estado |
|---|---|---|
| Aviso de privacidad (Art. 15-16) | Template personalizable por médico. Mostrado en registro de paciente. Aceptación en tabla `avisos_privacidad` | ✅ |
| Consentimiento datos sensibles | Campo `consentimiento_datos_sensibles` (datos de salud = sensibles bajo LFPDPPP) | ✅ |
| Derechos ARCO | Proceso documentado. MVP: solicitudes vía email, manejo manual. Fase 2: API self-service | 🔄 |
| Portabilidad de datos | Fase 2: exportación estructurada (JSON + PDF) de todos los datos del paciente | 🔄 |
| Notificación de brecha | Protocolo documentado en `docs/legal/breach_protocol.md`. 72 horas máximo (INAI) | ✅ |
| Acuerdo de procesamiento | Template en `docs/legal/` para relación médico (responsable) ↔ plataforma (encargado) | ✅ |

---

## 🚀 Guía de Instalación

### Pre-requisitos

```bash
# Herramientas necesarias
aws --version          # >= 2.0
terraform --version    # >= 1.7
python --version       # >= 3.12
node --version         # >= 20
docker --version       # >= 24
```

### 1. Configurar AWS

```bash
# Crear perfil de AWS con permisos de administrador
aws configure --profile medrecord-prod

# Variables de entorno necesarias
export AWS_PROFILE=medrecord-prod
export AWS_DEFAULT_REGION=us-east-1
```

### 2. Bootstrap de Terraform

```bash
# Crear el backend de Terraform (S3 + DynamoDB para state locking)
cd terraform/scripts
chmod +x init.sh
./init.sh medrecord-terraform-state

# Inicializar cada ambiente
cd terraform/environments/dev
terraform init
terraform plan
terraform apply
```

### 3. Levantar backend local

```bash
cd backend

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno para desarrollo
cp .env.example .env.local
# Editar .env.local con tus credenciales locales

# Migraciones de base de datos
alembic upgrade head

# Levantar servidor de desarrollo
uvicorn app.main:app --reload --port 8000
```

### 4. Levantar frontend local

```bash
cd frontend

npm install
npm run dev
# App disponible en http://localhost:5173
```

---

## 🔑 Variables de Entorno

### Backend (Lambda / local)

```bash
# Base de datos (en prod: obtener de Secrets Manager)
DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:...

# KMS — Cifrado (envelope encryption)
KMS_ENCRYPTION_KEY_ID=arn:aws:kms:us-east-1:...

# KMS — Firma electrónica (ECDSA)
KMS_SIGNING_KEY_ID=arn:aws:kms:us-east-1:...

# S3
S3_EXPEDIENTES_BUCKET=medrecord-expedientes-prod
S3_AUDIT_BUCKET=medrecord-audit-prod
S3_CONSENT_BUCKET=medrecord-consentimientos-prod

# Cognito
COGNITO_USER_POOL_ID=us-east-1_...
COGNITO_CLIENT_ID=...

# App
ENVIRONMENT=production  # development|staging|production
LOG_LEVEL=INFO
SECRETS_CACHE_TTL=300   # 5 minutos
DEK_CACHE_TTL=300       # 5 minutos
```

---

## 🧪 Testing

```bash
cd backend

# Tests unitarios
pytest tests/unit/ -v

# Tests de integración (requiere Docker para BD local)
pytest tests/integration/ -v

# Tests de cumplimiento normativo (LOS MÁS IMPORTANTES)
pytest tests/nom_compliance/ -v

# Tests de seguridad (RLS, firma, cifrado)
pytest tests/security/ -v

# Cobertura
pytest --cov=app --cov-report=html tests/
```

### Tests de cumplimiento NOM críticos

```python
# tests/nom_compliance/test_nom004.py

def test_expediente_requiere_campos_obligatorios():
    """NOM-004 §5.3: nombre, fecha_nacimiento y sexo son obligatorios"""
    ...

def test_nota_medica_requiere_firma():
    """NOM-004 §5.8: toda nota debe tener nombre y firma del médico"""
    ...

def test_nota_firmada_es_inmutable():
    """NOM-024: una nota firmada no puede modificarse"""
    ...

def test_audit_log_registra_todo_acceso():
    """NOM-004: todo acceso al expediente debe quedar registrado"""
    ...

def test_conservacion_minima_5_años():
    """NOM-004: el expediente debe conservarse al menos 5 años"""
    ...
```

### Tests de seguridad críticos

```python
# tests/security/test_rls.py

def test_rls_impide_acceso_cross_tenant():
    """Doctor A no puede ver pacientes de Doctor B"""
    ...

def test_rls_impide_bypass_sin_tenant_context():
    """Sin SET LOCAL app.current_tenant, no se ven datos"""
    ...

# tests/security/test_firma.py

def test_firma_ecdsa_es_verificable():
    """kms:Verify debe retornar TRUE para firma válida"""
    ...

def test_contenido_modificado_invalida_firma():
    """Modificar contenido después de firmar debe fallar verificación"""
    ...

# tests/security/test_encryption.py

def test_envelope_encryption_aislamiento_tenant():
    """DEK de tenant A no puede descifrar datos de tenant B"""
    ...
```

---

## 🔄 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml (resumen)
on: [pull_request]
jobs:
  test:
    - pytest tests/ (unit + integration + nom_compliance + security)
    - terraform fmt --check
    - terraform validate
    - checkov -d terraform/  # Security scanning IaC

  deploy-staging:           # Solo en merge a main
    - terraform apply staging
    - pytest tests/e2e/ --env=staging

  deploy-prod:              # Manual approval requerido
    - Requiere aprobación manual
    - terraform apply prod
    - Smoke tests
    - Alerta a Slack/Email
```

---

## 📈 Roadmap

### Fase 1 — MVP (Semanas 1-10)
- [ ] Infraestructura AWS: VPC, Aurora, KMS, Cognito, S3, WAF (Sem 1-2)
- [ ] Schema BD + RLS + envelope encryption (Sem 3-4)
- [ ] API: Pacientes, Expedientes, Notas + firma ECDSA (Sem 3-6)
- [ ] API: Consentimientos, aviso de privacidad (Sem 5-6)
- [ ] Frontend: auth, dashboard, CRUD completo, firma UX (Sem 7-8)
- [ ] Observabilidad: 5 alarmas + health check + DLQ (Sem 9)
- [ ] Beta con 3-5 médicos piloto (Sem 10)

### Fase 2 — Crecimiento (Mes 4-6)
- [ ] Agenda de citas con recordatorios SMS/WhatsApp
- [ ] Receta electrónica con código QR
- [ ] API self-service para derechos ARCO (LFPDPPP)
- [ ] Exportación de datos del paciente (portabilidad)
- [ ] Facturación CFDI 4.0 integrada
- [ ] App móvil (React Native)

### Fase 3 — Escala (Mes 7-12)
- [ ] IA: transcripción automática de consulta (Whisper)
- [ ] IA: generación de notas SOAP desde transcripción
- [ ] Interoperabilidad con IMSS Digital (FHIR R4)
- [ ] Cross-region DR (S3 + Aurora Global Database)
- [ ] Telemedicina (WebRTC)
- [ ] Marketplace de especialistas

---

## 🤝 Contribuir

```bash
# Flujo de trabajo
git checkout -b feature/mi-feature
# ... cambios ...
git commit -m "feat(expedientes): agregar validación CURP"
git push origin feature/mi-feature
# Abrir PR → CI corre automáticamente
```

### Convenciones de commits
```
feat:     nueva funcionalidad
fix:      corrección de bug
nom:      cambio relacionado con cumplimiento NOM
security: cambio relacionado con seguridad
infra:    cambio de infraestructura Terraform
docs:     documentación
```

---

## 📜 Licencia y Cumplimiento Legal

Este software está diseñado para cumplir con:

- **NOM-004-SSA3-2012** — Del expediente clínico
- **NOM-024-SSA3-2012** — Sistemas de información de registro electrónico para la salud
- **Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP)**
- **Decreto de Digitalización del Sector Salud** (enero 2026)

> ⚠️ **Aviso:** Este software es una herramienta técnica. El cumplimiento normativo final es responsabilidad del establecimiento médico que lo utiliza. Se recomienda auditoría legal periódica con un especialista en derecho sanitario mexicano.

---

## 📞 Contacto y Soporte

- **Issues técnicos:** GitHub Issues
- **Seguridad (vulnerabilidades):** security@medrecord.mx (PGP disponible)
- **Consultas NOM:** compliance@medrecord.mx
- **Privacidad (ARCO):** privacidad@medrecord.mx

---

*Construido con ❤️ en México · NOM-004 + NOM-024 + LFPDPPP · AWS Well-Architected*