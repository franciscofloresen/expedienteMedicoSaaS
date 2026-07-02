# CloudMedRecord - Technical Architecture & Spec (Ponytail Edition 👱‍♀️)

> **"Build the minimum that works. No unrequested abstractions, no avoidable dependencies, no boilerplate."**

Este documento detalla la arquitectura técnica, los flujos de datos y la estrategia de infraestructura de CloudMedRecord. Está escrito para consumo directo de ingeniería. Sin paja, puro músculo.

## 1. Visión General del Sistema
CloudMedRecord es un SaaS de Expediente Clínico Electrónico (ECE) diseñado para cumplir estrictamente con la normativa mexicana (**NOM-004-SSA3-2012** y **NOM-024-SSA3-2012**) con la menor complejidad de código posible. 

**Core Philosophy:** Delegar responsabilidades pesadas a servicios de terceros confiables (Clerk para Auth, AWS/GCP manejado vía Terraform) y mantener la lógica de negocio puramente funcional y stateless en el backend.

## 2. Stack Tecnológico (The Pragmatic Choice)

### Frontend (SPA)
*   **Core:** React + TypeScript (Vite). Tipado estricto sin YAGNI.
*   **Estado de Servidor:** `TanStack Query` (React Query). Nada de Redux. El backend es la única fuente de verdad; React Query solo cachea y sincroniza.
*   **Auth:** `@clerk/react`. Offload completo de JWT, sesión, 2FA y gestión de usuarios.
*   **UI/Estilos:** CSS puro (CSS Variables + Grid/Flexbox) inyectado globalmente. Cero dependencias pesadas de UI kits. Responsive de forma nativa.

### Backend (REST API)
*   **Framework:** FastAPI (Python). Rápido, concurrencia asíncrona nativa (`async/await`) y generación automática de OpenAPI/Swagger.
*   **Database:** PostgreSQL 15. Robusto, transaccional.
*   **ORM / Migraciones:** SQLAlchemy + Alembic.
*   **Gestión de Entorno:** `pyproject.toml`, entorno virtual estándar. 

### Infraestructura (IaC)
*   **Orquestación Local:** Docker Compose (levantar BD con 1 comando).
*   **Infra y Despliegue:** Terraform para aprovisionar los recursos en la nube. 

---

## 3. Arquitectura y Escalabilidad

### Stateless Backend
FastAPI opera de manera 100% *stateless*. Cada request incluye un Bearer Token (JWT de Clerk) que se valida en el middleware. Esto permite:
*   **Auto-scaling Horizontal:** Puedes levantar 1 o 100 contenedores del backend detrás de un Load Balancer sin preocuparte por *sticky sessions*.
*   **Resiliencia:** Si un pod/instancia muere, otra toma el request inmediatamente. Cero estado en memoria.

### Multi-Tenancy (Aislamiento de Clínicas)
La base de datos utiliza un modelo lógico de **Row-Level Security (RLS)** o filtrado estricto por `tenant_id` en las queries de SQLAlchemy.
*   Los datos de la Clínica A jamás cruzan con la Clínica B. 
*   **Por qué no esquemas por tenant:** Sobrecarga innecesaria en las migraciones de Alembic. Un UUID indexado para `tenant_id` en las tablas maestras es suficientemente rápido y escalable hasta decenas de millones de registros.

---

## 4. Pilares de Seguridad y Cumplimiento (NOM-004 / NOM-024)

### Autenticación y Autorización (Clerk)
*   El backend no almacena contraseñas.
*   Mitigación nativa contra fuerza bruta, inyecciones en login, y soporte para SSO/2FA delegado completamente a la infraestructura de Clerk.

### Cifrado de Datos Sensibles (Encryption at Rest)
El script `update_dummy_dek.py` y la arquitectura sugieren un patrón de seguridad avanzado: **Envelope Encryption**.
*   **Data Encryption Key (DEK):** Los datos demográficos sensibles (domicilios, contactos) de los pacientes se cifran a nivel de base de datos o aplicación antes de tocar el disco duro.
*   Si un atacante realiza un dump de PostgreSQL, la información sensible sigue cifrada.

### Inmutabilidad y Auditoría Criptográfica (El "Golden Standard")
Para cumplir con la NOM-024 (Trazabilidad y Autenticidad):
1.  **Notas Médicas como Borradores:** Mientras la nota está abierta, es un `UPDATE` normal.
2.  **Firma y Sellado:** Al presionar "Firmar y Bloquear", el sistema genera un **Hash criptográfico (SHA-256)** del contenido de la nota concatenado con los datos del médico (`firma_hash_contenido`).
3.  **Inmutabilidad (Append-Only):** A partir de ese momento, la nota entra en estado "Firmada" (locked = true). Las reglas a nivel aplicación (y potencialmente triggers en la DB) rechazan cualquier `UPDATE` o `DELETE`. 
4.  Cualquier corrección futura exige una **Adenda**, protegiendo legalmente al médico y asegurando el rastro de auditoría.

### Archivo en lugar de Borrado (Soft-Deletes)
*   Los pacientes no se borran (NOM-004 exige 5 años de conservación).
*   Al "eliminar", se hace un *Soft Delete* (por ejemplo, `is_active = False` o `deleted_at = TIMESTAMP`), ocultándolo de la UI pero preservándolo en DB ante una auditoría de la COFEPRIS/SSA.

---

## 5. Resiliencia y Manejo de Errores

1.  **Frontend (Graceful Degradation):** Error Boundaries en React interceptan caídas en la UI. React Query maneja retries exponenciales si la red fluctúa o si el backend temporalmente rechaza conexiones (503/502).
2.  **Transacciones Atómicas (Backend):** Toda operación que involucre múltiples tablas (ej. crear paciente + crear expediente + log de auditoría) se encapsula en un `db.session.commit()`. Si algo falla, se ejecuta `db.session.rollback()`. No hay "datos a medias".
3.  **Database Connection Pooling:** SQLAlchemy gestiona un pool de conexiones persistentes a PostgreSQL para evitar el overhead del handshake TCP en cada request, garantizando alta latencia baja y alto throughput (RPS).

---

## 6. Filosofía "Ponytail" en este Proyecto

*   **Sin sobreingeniería:** No usamos microservicios, no usamos Kafka, no usamos Kubernetes complejo. Es un Monolito Modular rápido en FastAPI.
*   **El código como pasivo:** Cada línea de código extra es una línea que hay que mantener. La delegación a Clerk, TanStack Query y Postgres (en lugar de bases de datos exóticas) minimiza el mantenimiento a largo plazo.
*   **Focus en el Negocio:** La arquitectura garantiza seguridad extrema (lo cual es vital en HealthTech) sin sacrificar la velocidad de desarrollo de nuevos *features*.
