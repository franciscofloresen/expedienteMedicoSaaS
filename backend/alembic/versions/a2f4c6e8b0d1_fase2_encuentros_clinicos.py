"""fase2 encuentros clinicos

Revision ID: a2f4c6e8b0d1
Revises: efb69dbb7dfb
Create Date: 2026-07-15

Fase 2 del ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2 (§5.2/§6.3): introduce el
**encuentro clínico** (``encuentros_clinicos``) — la atención real, distinta de la
agenda (``citas``). Separarlos evita clasificar una cita cancelada como primera
consulta.

Migración **solo esquema** (§1.5): tabla nueva + índice único parcial + una columna
NULLABLE en ``notas``. No hay backfill sobre filas clínicas existentes → la clase de
cambio que nunca ha roto prod aquí.

Regla de oro respetada (§1.1): **cero UPDATE a notas firmadas**. ``notas`` solo recibe
un ``ADD COLUMN`` nullable sin default — metadata-only, no toca ninguna fila, así que
el trigger de inmutabilidad ``notas_signed_immutable`` (que es ``FOR EACH ROW`` en
UPDATE) jamás se dispara. La columna se escribe **solo al crear** notas nuevas; para
notas históricas el vínculo vive del lado del encuentro (``nota_inicial_id``).

Tenant-scoped (§1.2): RLS ``ENABLE`` + ``FORCE`` + política
``tenant_isolation_encuentros_clinicos`` y ``REVOKE DELETE`` + trigger
``prevent_encuentros_clinicos_deletion`` (reusa la función compartida
``prevent_clinical_deletion``). ``tenant_id`` propia porque RLS no sigue FKs.

Enforcement de "una sola primera vez" (§3): índice único parcial
``uq_encuentro_primera_vez`` sobre ``(tenant_id, paciente_id)`` filtrado a
``tipo='primera_vez' AND estado='completado'`` — a prueba de carreras, no validación
transaccional.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2f4c6e8b0d1"
down_revision: Union[str, None] = "efb69dbb7dfb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "encuentros_clinicos"


def upgrade() -> None:
    # ── 1. Esquema de encuentros_clinicos (sin RLS todavía) ──
    op.create_table(
        _TABLE,
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("paciente_id", UUID(as_uuid=True), sa.ForeignKey("pacientes.id"), nullable=False),
        sa.Column(
            "expediente_id", UUID(as_uuid=True), sa.ForeignKey("expedientes.id"), nullable=False
        ),
        sa.Column("cita_id", UUID(as_uuid=True), sa.ForeignKey("citas.id")),
        sa.Column("medico_id", UUID(as_uuid=True), sa.ForeignKey("medicos.id"), nullable=False),
        sa.Column(
            "credencial_id", UUID(as_uuid=True), sa.ForeignKey("medico_credenciales.id")
        ),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="subsecuente"),
        sa.Column("estado", sa.String(20), nullable=False, server_default="programado"),
        sa.Column(
            "clasificacion_origen", sa.String(20), nullable=False, server_default="automatica"
        ),
        sa.Column("motivo_correccion", sa.Text),
        # FK a notas: la nota inicial que produjo el encuentro. use_alter no aplica en
        # SQL (notas ya existe), pero declaramos el nombre para consistencia con el modelo.
        sa.Column(
            "nota_inicial_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notas.id", name="fk_encuentro_nota_inicial"),
        ),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True)),
        sa.Column("fecha_fin", sa.DateTime(timezone=True)),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("creado_por", UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "tipo IN ('primera_vez', 'subsecuente', 'procedimiento', 'urgencia', 'otro')",
            name="encuentros_clinicos_tipo_check",
        ),
        sa.CheckConstraint(
            "estado IN ('programado', 'iniciado', 'completado', 'cancelado')",
            name="encuentros_clinicos_estado_check",
        ),
        sa.CheckConstraint(
            "clasificacion_origen IN ('automatica', 'manual', 'migracion')",
            name="encuentros_clinicos_clasificacion_origen_check",
        ),
    )
    op.create_index("ix_encuentros_clinicos_tenant_id", _TABLE, ["tenant_id"])
    op.create_index(
        "ix_encuentros_clinicos_paciente_estado",
        _TABLE,
        ["tenant_id", "paciente_id", "estado"],
    )
    op.create_index("ix_encuentros_clinicos_fecha_inicio", _TABLE, ["fecha_inicio"])
    # Enforcement de "una sola primera vez completada" por paciente/tenant (§3).
    op.create_index(
        "uq_encuentro_primera_vez",
        _TABLE,
        ["tenant_id", "paciente_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'primera_vez' AND estado = 'completado'"),
    )

    # ── 2. Vínculo create-only en notas: ADD COLUMN nullable (§1.1) ──
    # Metadata-only, sin default → no toca ninguna fila → el trigger de inmutabilidad
    # (FOR EACH ROW en UPDATE) nunca se dispara. Se escribe solo al crear notas nuevas.
    op.add_column(
        "notas",
        sa.Column(
            "encuentro_clinico_id",
            UUID(as_uuid=True),
            sa.ForeignKey("encuentros_clinicos.id", name="fk_nota_encuentro_clinico"),
        ),
    )

    # ── 3. RLS + política + grants ──
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {_TABLE} TO medrecord_app")
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_TABLE} ON {_TABLE}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )

    # ── 4. Protección de borrado: rol + trigger (§5.1) ──
    # Un encuentro es evidencia clínica: se cancela (estado), nunca se borra.
    op.execute(f"REVOKE DELETE ON {_TABLE} FROM medrecord_app")
    op.execute(f"DROP TRIGGER IF EXISTS prevent_{_TABLE}_deletion ON {_TABLE}")
    op.execute(
        f"""
        CREATE TRIGGER prevent_{_TABLE}_deletion
        BEFORE DELETE ON {_TABLE}
        FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS prevent_{_TABLE}_deletion ON {_TABLE}")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TABLE} ON {_TABLE}")
    op.execute(f"ALTER TABLE {_TABLE} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_TABLE} FROM medrecord_app")
    # Drop the notas FK column before the table it references.
    op.drop_column("notas", "encuentro_clinico_id")
    op.drop_table(_TABLE)
