"""Fase 8 clinical rollout contract.

One monotonic environment value controls the activation order agreed in the
roadmap. It is intentionally small: no flag service, no per-tenant state, and no
stage that can drop legacy columns. A code/config rollback only moves the stage
back; clinical evidence is never deleted or rewritten.
"""

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class RolloutStep:
    stage: int
    key: str
    description: str


ROLLOUT_STEPS: tuple[RolloutStep, ...] = (
    RolloutStep(1, "schema_compatibility", "Tablas nuevas y compatibilidad"),
    RolloutStep(2, "medico_credentials", "Perfil médico y credenciales"),
    RolloutStep(3, "clinical_encounters", "Encuentros clínicos"),
    RolloutStep(4, "first_visit_evolution", "Primera vez y evolución"),
    RolloutStep(5, "cie10_catalog", "Catálogo CIE-10 completo"),
    RolloutStep(6, "structured_diagnoses", "Diagnósticos normalizados"),
    RolloutStep(7, "consent_template_engine", "Motor de consentimientos"),
    RolloutStep(8, "consent_finalization", "Firmantes, testigos y documento final"),
    RolloutStep(9, "normative_library", "Biblioteca normativa"),
)

_STAGE_BY_KEY = {step.key: step.stage for step in ROLLOUT_STEPS}


def rollout_stage() -> int:
    return settings.clinical_rollout_stage


def feature_enabled(key: str) -> bool:
    """Return whether ``key`` is active; unknown keys fail closed."""
    required_stage = _STAGE_BY_KEY.get(key)
    return required_stage is not None and rollout_stage() >= required_stage


def rollout_summary() -> dict[str, object]:
    """Return non-sensitive operational state for logs/verifiers."""
    current = rollout_stage()
    return {
        "stage": current,
        "enabled": [step.key for step in ROLLOUT_STEPS if step.stage <= current],
        "next": next((step.key for step in ROLLOUT_STEPS if step.stage > current), None),
    }
