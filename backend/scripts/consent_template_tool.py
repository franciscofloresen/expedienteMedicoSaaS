"""Local validate/preview/compare tool for consent-template JSON artifacts."""

import argparse
import json
from datetime import date
from pathlib import Path

from app.services.consent_template_reviews import (
    phase6_readiness,
    phase7_dermatology_readiness,
)
from app.services.consent_templates import (
    DEFAULT_CATALOG_PATH,
    load_catalog,
    render_consent_content,
    version_hash,
)


def _validate(path: Path) -> int:
    documents = load_catalog(path)
    report = [
        {"template_key": doc.template_key, "version": doc.version, "hash": version_hash(doc)}
        for doc in documents
    ]
    print(json.dumps({"ok": True, "templates": report}, ensure_ascii=False, indent=2))
    return 0


def _preview(path: Path, key: str) -> int:
    documents = {doc.template_key: doc for doc in load_catalog(path)}
    document = documents.get(key)
    if document is None:
        raise ValueError(f"Plantilla desconocida: {key}")
    print(
        render_consent_content(
            template=document.runtime_template(),
            paciente_nombre="Paciente de ejemplo",
            medico_nombre="Dra. Ejemplo",
            medico_cedula="CEDULA-EJEMPLO",
            procedimiento=document.procedimiento or document.nombre,
            riesgos=document.contenido.riesgos,
            fecha=date.today(),
        )
    )
    return 0


def _compare(old_path: Path, new_path: Path) -> int:
    old = {doc.template_key: doc for doc in load_catalog(old_path)}
    new = {doc.template_key: doc for doc in load_catalog(new_path)}
    report = {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(
            key
            for key in set(old) & set(new)
            if version_hash(old[key]) != version_hash(new[key])
        ),
        "unchanged": sorted(
            key
            for key in set(old) & set(new)
            if version_hash(old[key]) == version_hash(new[key])
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _review_status(catalog: str) -> int:
    report = (
        phase7_dermatology_readiness() if catalog == "fase7_dermatologia" else phase6_readiness()
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("path", nargs="?", type=Path, default=DEFAULT_CATALOG_PATH)

    preview = subparsers.add_parser("preview")
    preview.add_argument("template_key")
    preview.add_argument("--path", type=Path, default=DEFAULT_CATALOG_PATH)

    compare = subparsers.add_parser("compare")
    compare.add_argument("old_path", type=Path)
    compare.add_argument("new_path", type=Path)

    review_status = subparsers.add_parser("review-status")
    review_status.add_argument(
        "--catalog",
        choices=("fase6", "fase7_dermatologia"),
        default="fase6",
    )

    args = parser.parse_args()
    if args.command == "validate":
        return _validate(args.path)
    if args.command == "preview":
        return _preview(args.path, args.template_key)
    if args.command == "review-status":
        return _review_status(args.catalog)
    return _compare(args.old_path, args.new_path)


if __name__ == "__main__":
    raise SystemExit(main())
