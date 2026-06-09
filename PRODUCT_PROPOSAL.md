# Product Proposal: [Nombre en Construcción] SaaS for Mexico

Date: 2026-06-04  
Scope reviewed: `README.md`, `market_report.html`, `docs/legal/`, current backend/frontend/Terraform structure, and official references for NOM-004, NOM-024, LFPDPPP, and AWS Well-Architected.

## Executive Opinion

Yes, this is a good proposal. The strongest version is not "another generic medical-record app"; it is a compliance-first, low-friction electronic clinical record for independent Mexican doctors and very small private practices.

The market thesis is plausible: many doctors do not want hospital-grade software, heavy implementation, large-clinic workflows, or expensive per-user pricing. A small, reliable, Mexican-norm-aware system with simple onboarding, signed notes, audit trails, privacy notices, consent tracking, and predictable pricing can be a real product.

However, the current pitch overclaims. The README and market report say "full compliance" and imply regulatory certainty before the product, controls, testing, operational procedures, and legal review are finished. I would change the positioning to:

> "Designed to help independent Mexican doctors operate electronic clinical records aligned with NOM-004, NOM-024, and privacy obligations, with verifiable audit, signature, retention, and security controls."

That wording is more credible. It sells the same value without creating legal and trust risk.

## Strategic Positioning

### Keep

- Focus on independent doctors and 1-5 doctor practices.
- Mexican compliance as the core differentiator.
- Low monthly price and low onboarding friction.
- Security, auditability, and clinical-note integrity as first-class product features.
- AWS serverless/Terraform direction for a lean team.

### Change

- Do not claim "cumplimiento total" until there is a compliance matrix, test evidence, operational runbooks, and legal review.
- Do not use competitor compliance claims unless they are sourced and periodically verified.
- Treat the "Decreto 2026" claim as unverified until there is a direct official source. Use it carefully in sales copy.
- Position AI as optional and later. The MVP should win on trust, speed, and compliance evidence first.
- Move from "feature-rich SaaS" to "legally careful clinical workflow that is hard to misuse."

## Proposed Product Thesis

### Target Customer

The first customer should be:

- Independent private doctor in Mexico.
- Has 100-1,500 active patients.
- Uses paper, spreadsheets, WhatsApp, Google Drive, or a generic tool.
- Wants to avoid expensive setup and long training.
- Needs confidence that records are complete, signed, retained, auditable, and private.

Avoid starting with hospitals, multi-site clinics, insurance integrations, labs, or public-sector workflows. Those customers add procurement, interoperability, support, and compliance complexity too early.

### MVP Promise

The MVP promise should be:

> "Create, maintain, sign, and retrieve a compliant electronic clinical record in under 10 minutes of setup."

### MVP Features

Required:

- Tenant onboarding for one doctor.
- Cognito login with MFA.
- Patient registry with NOM-004 required identification fields.
- Clinical record per patient.
- History, evolution note, diagnosis, treatment, vital signs, and attachments.
- Draft and signed note states.
- Digital signature metadata and verification.
- Immutable audit trail for all record access and changes.
- Privacy notice acceptance and explicit sensitive-data consent.
- Exportable clinical summary.
- Soft archive, not hard delete, for clinical data.
- Admin dashboard showing compliance status per patient.

Defer:

- Telemedicine.
- CFDI.
- AI summaries.
- Multi-region disaster recovery.
- Complex analytics.
- Lab integrations.
- Hospital workflows.
- Full FHIR interoperability unless required by certification path.

## Compliance Proposal

This needs to be treated as a compliance product, not only a CRUD app.

### NOM-004-SSA3-2012

NOM-004 is about the clinical record itself: content, ownership/responsibility, confidentiality, medical notes, history, consent documents, and retention. The product should enforce record completeness through workflow, validation, and visible compliance status.

Recommended controls:

- Required data model for patient identity and clinical history.
- Note-type-specific schemas.
- Server-side validation for every required field.
- Automatic timestamping.
- Doctor identity snapshot at signature time.
- Signed notes become immutable.
- Corrections must be amendments, not edits to signed content.
- Retention policy must prevent premature deletion.
- Consent documents must be attached, hashed, and auditable.

### NOM-024-SSA3-2012

NOM-024 applies to electronic health record information systems and covers secure processing, preservation, interpretation, and exchange of health information. The product should map every technical control to a compliance requirement.

Recommended controls:

- Strong authentication with MFA.
- Role-based access control, even if the first role model is simple.
- Tenant isolation with PostgreSQL RLS and application-level checks.
- Encryption in transit and at rest.
- Application-level encryption for high-risk clinical fields where feasible.
- Complete audit trail for access and modifications.
- Signed and verifiable clinical notes.
- Backups and restore testing.
- Export and portability strategy.
- Standards roadmap for interoperability.

### LFPDPPP and Privacy

Health data is sensitive personal data. The product should make privacy operational, not just documentary.

Recommended controls:

- Per-doctor customizable privacy notice.
- Explicit consent for sensitive health data.
- Separate acceptance for secondary purposes.
- ARCO request workflow.
- Breach response process.
- Data processor/controller role clarity in contracts.
- Log minimization so sensitive clinical content does not leak into observability tools.
- Data retention and deletion policies reviewed by counsel.

### Compliance Matrix

Create `docs/compliance_matrix.md` and track:

| Requirement | Product Control | Code Reference | Test Evidence | Operational Evidence | Status |
|---|---|---|---|---|---|
| Patient identity fields | Required schemas and DB constraints | Backend models/API | Unit + integration tests | Release checklist | Planned |
| Signed note immutability | DB trigger + API guard | Notes service | Security tests | Audit sample | Planned |
| Audit trail | Append-only DB log + WORM export | Audit middleware | Integration tests | CloudWatch/S3 evidence | Planned |
| Privacy consent | Consent table + UI acceptance | Consent API/UI | E2E tests | Tenant setup checklist | Planned |

Do not sell "full compliance" until this matrix has evidence.

## Architecture Proposal

### Recommended MVP Architecture

Use a single-region AWS architecture that is cheap but defensible:

- React + Vite frontend hosted on S3 and CloudFront.
- FastAPI backend on Lambda behind API Gateway.
- Cognito for authentication and MFA.
- PostgreSQL with RLS.
- KMS for envelope encryption and signing key management.
- S3 for attachments, consent PDFs, exports, and immutable audit exports.
- CloudWatch for logs and metrics.
- Terraform for all infrastructure.

### Database Choice

The README proposes Aurora Serverless v2 plus RDS Proxy. That is architecturally strong, but it may be more expensive than necessary before revenue.

Recommended stages:

| Stage | Doctors | Database | Reason |
|---|---:|---|---|
| Local/pilot | 1-5 | Docker PostgreSQL locally, disposable dev DB in AWS | Keep experimentation cheap |
| Paid MVP | 5-50 | RDS PostgreSQL `t4g.small` or Aurora Serverless v2 min 0.5 ACU | Choose based on operational preference and real cost |
| Growth | 50-300 | Aurora Serverless v2 + RDS Proxy | Better scaling and connection management |
| Larger clinics | 300+ | Aurora capacity tuning, read replicas only if metrics require | Avoid premature cost |

If the product is sold as "compliance-first", do not make the cheapest database choice if it weakens backups, recovery, encryption, or operational reliability. Cheap must mean right-sized, not fragile.

### Signature Strategy

Use a shared KMS asymmetric signing key for MVP only if the signed payload itself contains all legal and audit context:

- tenant ID
- doctor user ID
- doctor name
- professional license
- note ID
- patient/expediente ID
- canonical note content hash
- signing timestamp
- algorithm and key ID

Store all of that signature metadata. Add verification. Add append-only audit events for signing. If later legal review says a stronger identity-bound signature is required, migrate to a more robust model.

Do not rely on undocumented or unsupported KMS context behavior. The canonical signed payload is the safer source of truth.

### Audit Strategy

Audit must be a product feature:

- Write audit records to the database synchronously for clinical reads/writes/signing.
- Export audit records to S3 with Object Lock for WORM retention.
- Keep structured CloudWatch logs, but do not treat CloudWatch as the primary audit ledger.
- Add query screens for doctors to see access history.
- Add internal anomaly detection later.

### Tenant Isolation

Use defense in depth:

- JWT tenant claim.
- API-level authorization.
- PostgreSQL RLS with `WITH CHECK` policies.
- Non-superuser app role.
- Database triggers for tenant consistency across related rows.
- Tests that attempt cross-tenant reads and writes.

## Well-Architected Proposal

AWS currently frames Well-Architected around six pillars: operational excellence, security, reliability, performance efficiency, cost optimization, and sustainability. The README should update "5 pillars" to "6 pillars."

### Operational Excellence

- CI for backend, frontend, Terraform, and migrations.
- Runbooks for KMS failure, audit failure, DB outage, suspicious access, and restore.
- Versioned releases and migration rollback plans.
- Feature flags for high-risk clinical workflow changes.

### Security

- MFA enforced.
- Least-privilege IAM.
- Secrets Manager for credentials.
- KMS for encryption/signing.
- RLS and API authorization.
- WAF only when public traffic exists and cost is justified.
- Security tests in CI.

### Reliability

- Automated backups.
- Restore drills.
- Dead-letter queues where async jobs exist.
- Health checks.
- CloudWatch alarms.
- No multi-region DR until the business has enough revenue or contractual need.

### Performance Efficiency

- Serverless API is acceptable for the first customer segment.
- Avoid provisioned concurrency until users complain or metrics prove need.
- Cache JWKS, secrets, and DEKs carefully.
- Add database indexes based on query patterns.

### Cost Optimization

- Single region.
- No CloudHSM in MVP.
- No per-tenant signing keys in MVP unless legal review requires them.
- No provisioned concurrency initially.
- No read replicas initially.
- S3 lifecycle for attachments and exports.
- Use budgets and cost anomaly alerts from day one.

### Sustainability

- Right-size compute.
- Use managed services instead of always-on custom infrastructure.
- Lifecycle old objects to colder storage.
- Avoid unused staging/prod resources during early development.

## Code Quality Proposal

### Backend

- Keep FastAPI and SQLAlchemy async.
- Add typed service layers for audit, signing, consent, tenant onboarding, and notes.
- Avoid duplicating `get_tenant_db` in each router.
- Centralize authorization dependencies.
- Use Pydantic schemas per note type.
- Add Alembic migrations for every DB policy, trigger, and constraint.
- Add integration tests with PostgreSQL, not only unit tests.
- Use Python 3.12 consistently with `.python-version` or `uv`.

### Frontend

- Replace `any` types with API DTOs.
- Move API URL and dev tenant behavior to environment config.
- Add auth state and token injection.
- Replace `alert()` and `confirm()` with real UI states.
- Build clinical workflows around "draft -> review -> sign -> locked".
- Add responsive layouts.
- Add frontend build/lint CI.

### Testing

Minimum release gates:

- Unit tests for validators, canonical serialization, encryption, signing.
- Integration tests for tenant isolation, audit persistence, signed-note immutability.
- API tests for auth failure, missing tenant, cross-tenant access.
- Migration tests that prove RLS is enabled.
- Frontend build and key workflow tests.
- Manual restore drill before production launch.

## Cost Proposal

The project can be cheap if the architecture is staged.

### MVP Monthly Infrastructure Target

Target: USD $50-$120/month before significant scale.

Expected cost drivers:

- Database baseline cost.
- RDS Proxy if used.
- WAF if enabled early.
- CloudWatch log volume.
- KMS calls.
- Secrets Manager secrets.

### Recommended Cost Decisions

- Keep one AWS region.
- Start without provisioned concurrency.
- Start without multi-region DR.
- Start without CloudHSM.
- Start without Bot Control.
- Use S3 lifecycle rules.
- Add AWS Budgets immediately.
- Revisit Aurora vs RDS based on real pilot workload.

### Pricing Recommendation

Keep the pricing simple:

| Plan | Price | Best For | Notes |
|---|---:|---|---|
| Basico | $299 MXN/month | Solo doctor starting out | Patient cap, core EHR, signed notes |
| Profesional | $499 MXN/month | Main plan | Unlimited active patients, consent, audit exports, priority support |
| Consultorio | $899-$1,299 MXN/month | 2-5 doctors | Shared admin, roles, separate doctor signatures |

Do not include AI in the cheapest plan. It raises privacy, cost, and clinical-safety questions.

## What I Would Change in the Business Proposal

1. Replace "full compliance" with "compliance-aligned, evidence-backed controls."
2. Verify or remove the "Decreto 2026" claim unless an official legal source is attached.
3. Add legal review as a milestone, not an afterthought.
4. Build a public trust page showing security controls, retention, audit, and privacy posture.
5. Use the compliance matrix as a sales artifact once implemented.
6. Focus the first 10 pilots on one or two specialties, not every doctor type.
7. Offer migration from paper/spreadsheet as a paid onboarding service.
8. Avoid integrations until the core clinical workflow is excellent.

## Proposed Roadmap

### Phase 1: Credible MVP, 8-10 Weeks

- Reproducible dev environment.
- Working auth and tenant onboarding.
- Patient and expediente CRUD.
- Evolution notes with validation.
- Draft/review/sign/lock workflow.
- Audit persistence.
- RLS in migrations.
- Privacy notice and sensitive-data consent.
- Frontend build/lint/test CI.
- One deployable AWS environment.

Exit criteria:

- 3-5 doctors can use it with real-world sample data.
- Signed notes verify.
- Audit records exist for every record access.
- Cross-tenant tests pass.
- Legal/compliance review has identified no release-blocking issues.

### Phase 2: Paid Pilot, 6-8 Weeks

- Better UI for daily clinical use.
- Patient search and record summary.
- Consent documents and attachments.
- Export clinical summary.
- Backup restore drill.
- Support and incident process.
- Cost dashboard.
- First billing flow.

Exit criteria:

- 10 paying doctors.
- Less than 2 minutes to create a normal evolution note.
- No manual database work needed for onboarding.
- Support load is understood.

### Phase 3: Growth, 8-12 Weeks

- Appointment schedule.
- Prescription workflow if legally reviewed.
- Multi-doctor consultorio plan.
- Compliance dashboard.
- ARCO request management.
- Better reporting.
- Optional AI only after privacy and clinical risk review.

## Main Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Compliance overclaiming | High | Use compliance matrix, legal review, careful marketing |
| Audit trail incomplete | High | Make audit persistence a release blocker |
| Signed notes not legally credible | High | Store full metadata, verify signatures, review legal requirements |
| Tenant isolation bug | High | RLS with tests and non-superuser app role |
| Product too broad | Medium | Stay focused on solo doctors and core clinical record |
| Costs creep before revenue | Medium | Stage architecture, use budgets, avoid premature DR/CloudHSM |
| UX too slow for doctors | Medium | Pilot with real doctors early, measure note time |

## Final Recommendation

Proceed, but tighten the promise.

This is a strong project if it becomes the simplest credible compliance-first EHR for independent Mexican doctors. The winning version is not the one with the most features. It is the one that makes the doctor confident that every record is complete, signed, private, retrievable, auditable, and inexpensive to operate.

The next major milestone should be a small paid pilot, not a broad production launch. Before that pilot, the product must have working auth, tenant isolation, audit persistence, signed-note verification, privacy consent, retention protections, and a reproducible deployment.

## Sources to Keep Attached to the Proposal

- NOM-004-SSA3-2012, Del expediente clinico, DOF: https://www.dof.gob.mx/nota_detalle.php?codigo=5272787&fecha=15/10/2012
- NOM-024-SSA3-2012, Sistemas de informacion de registro electronico para la salud, DOF: https://www.dof.gob.mx/normasOficiales/4956/SALUD1/SALUD1.html
- Ley Federal de Proteccion de Datos Personales en Posesion de los Particulares, DOF reform publication: https://www.dof.gob.mx/nota_detalle.php?codigo=5752569&fecha=20/03/2025
- AWS Well-Architected Framework pillars: https://docs.aws.amazon.com/wellarchitected/latest/framework/the-pillars-of-the-framework.html

