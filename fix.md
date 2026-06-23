### DELETE-LIST

**Frontend**

- `framer-motion` (package.json): ~140KB of bloat for simple fades.
- `date-fns-tz` (package.json): Unused.
- `axios` (package.json): Overkill.
- `src/assets/vite.svg`, `src/assets/hero.png`: Dead assets.
- `.aurora-*`, `.auth-*` (index.css): Unused styles. Auth is handled by external modals.

**Backend & Root**

- `app/core/resilience.py`: Unused `@retry` wrappers (duplicated inline in `firma.py`).
- `slowapi` (main.py, pyproject.toml): Redundant. API Gateway handles rate limiting.
- `email-validator` (pyproject.toml): Unused.
- 5 speculative NOM-004 validators in `app/core/nom_validator.py` (`NotaIngreso`, `NotaEgreso`, etc.) that the frontend cannot yet trigger.
- Throwaway root scripts: `fix*.py`, `test_*.py`, `cleanup_db.py`, `example.html`, `market_report.html`, `error.txt`, `cmds.txt`.
- Overlapping review docs: Delete all except `PRODUCTION_ROADMAP.md` and the latest security audit status.

**IaC (Terraform)**

- `terraform/environments/staging/`: Speculative environment.
- `aws_db_proxy` in `database/main.tf`: Unnecessary for 50 tenants on Aurora Serverless v2.
- `terraform.tfstate` and `.terraform.lock.hcl` committed to source control: Run `git rm --cached`.

---

### REFACTORING SUGGESTIONS

**Frontend**

- **Native HTML5 Modals & Dates:** Replace `CitaModal.tsx` custom chrome with the native HTML5 `<dialog>` element. Replace any custom date picker wrappers with native `<input type="date">` or `<input type="datetime-local">`.
- **Native Fetch:** Replace `axios` interceptors with a thin native `fetch` wrapper.
- **CSS Animations:** Replace Framer Motion `<AnimatePresence>` page transitions with native CSS View Transitions and `@starting-style` for simple component fades.
- **De-duplication:** Extract the massive inline `style={{}}` objects repeated across all `NavLink` components in `Layout.tsx` into a single CSS utility class.

**Backend**

- **Flatten DTOs:** Strip out redundant Pydantic schema wrappers where read-only endpoints can safely return SQLAlchemy models directly. Derive `PacienteUpdate` directly from `PacienteCreate`.
- **Deprecated Entities:** Remove any service-layer or API routing logic for `AvisoPrivacidad` and `Consentimiento` if they are not fully wired up. Keep only their SQLAlchemy definitions in `models/` so Alembic preserves the compliance schema.

**IaC (Terraform)**

- **Consolidate Environments:** Stop copy-pasting module routing. Delete the `dev` and `prod` directories entirely and use a single root `main.tf` driven by `dev.tfvars` and `prod.tfvars`.
- **Variable Cleanup:** Remove the dangling `api_gateway_arn` and `sns_alarm_topic_arn` variables from the `security/main.tf` monolith.
