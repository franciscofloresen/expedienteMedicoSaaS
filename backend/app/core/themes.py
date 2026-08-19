"""Fase 13A — versioned theme allowlist.

Five visual families in light and dark = 10 themes. This is the backend half of
the shared, typed catalog (the frontend ThemeProvider carries the matching keys
and the actual token values). The API validates only against these KEYS and never
stores or emits a color. ``clinical-teal-dark`` is the current default and must
render identically to today's UI.

Keep this list in lockstep with ``frontend/src/theme/themes.ts``.
"""

DEFAULT_THEME = "clinical-teal-dark"

THEME_KEYS: frozenset[str] = frozenset(
    {
        "clinical-teal-dark",
        "clinical-teal-light",
        "sapphire-dark",
        "sapphire-light",
        "indigo-dark",
        "indigo-light",
        "emerald-dark",
        "emerald-light",
        "plum-dark",
        "plum-light",
    }
)


def is_valid_theme(tema: str) -> bool:
    return tema in THEME_KEYS
