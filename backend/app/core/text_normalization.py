"""Accent- and case-insensitive text normalization for CIE-10 search.

Single source of truth (roadmap §3): both the catalog importer (which populates
``cie10.normalized_description``) and the search endpoint (which normalizes the query)
call :func:`normalize_clinical_text`, so the GIN trigram index and the query live in the
same normalized space. Normalization is done here in Python — NOT with PostgreSQL's
``unaccent()`` in the index expression, because ``unaccent()`` is not immutable and
cannot back a functional index safely.
"""

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_clinical_text(value: str | None) -> str:
    """Lowercase, strip accents/diacritics, and collapse whitespace.

    ``"CÓLERA, no  especificado"`` → ``"colera, no especificado"``. Returns an empty
    string for ``None``/blank so callers can store a non-null normalized column.
    """
    if not value:
        return ""
    # NFKD splits accented letters into base + combining mark; drop the marks.
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WHITESPACE_RE.sub(" ", without_accents).strip().lower()
