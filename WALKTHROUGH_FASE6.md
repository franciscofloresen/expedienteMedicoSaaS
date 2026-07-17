# Walkthrough — Fase 6: biblioteca normativa inicial

## Resultado

La Fase 6 incorpora un paquete candidato de 19 documentos normativos sin migraciones ni
recursos AWS nuevos. El catálogo publicado de Fase 4 permanece intacto mientras se
completan las revisiones profesionales.

La entrega separa explícitamente:

- 14 cartas de `consentimiento_informado`;
- 1 `autorizacion` para captura y uso de fotografías clínicas;
- 4 `documento_relacionado`: representación/tutela, negativa, revocación y egreso
  voluntario.

Esta distinción evita presentar una negativa, revocación o autorización de datos como si
fuera el consentimiento informado del acto médico.

## Artefactos

- `backend/app/data/consent_templates_phase6.json`: 19 textos candidatos con campos,
  firmantes, testigos y referencias normativas.
- `backend/app/data/consent_template_reviews_phase6.json`: manifiesto nominativo de doble
  revisión por `template_key` y versión.
- `backend/app/services/consent_template_reviews.py`: valida cobertura exacta, identidad de
  versiones, referencias, clasificación y evidencia de aprobación.

Los textos contienen un aviso visible de borrador y `responsable_revision` / `revisada_en`
vacíos. Esto es intencional: no se atribuyó a un profesional una aprobación que no ha
realizado.

## Compuerta de publicación

Cada una de las 19 versiones requiere dos aprobaciones:

1. Clínica: nombre, cédula o rol verificable, fecha y enlace o identificador de evidencia.
2. Jurídica sanitaria: nombre, rol, fecha y enlace o identificador de evidencia.

Además, el artefacto candidato debe consolidar los responsables en
`responsable_revision` y la fecha en `revisada_en`. Mientras falte cualquiera de esos
datos, mientras alguno de los dos nombres no coincida con el manifiesto o mientras el
aviso siga marcado `BORRADOR`, tanto el dry-run como el apply de Fase 6 devuelven
`ok=false` antes de abrir una sesión de base de datos.

Estado local:

```bash
cd backend
python -m scripts.consent_template_tool validate app/data/consent_templates_phase6.json
python -m scripts.consent_template_tool review-status
python -m scripts.consent_template_tool preview cirugia_mayor \
  --path app/data/consent_templates_phase6.json
```

`review-status` termina con código 1 mientras exista una revisión pendiente. Al completar
el manifiesto debe terminar con código 0 y reportar 19 revisiones clínicas y 19 jurídicas
aprobadas.

## Operación en producción

El workflow `Ops — Consent Templates (Production)` acepta `catalog=fase6` y conserva el
patrón seguro de fases anteriores:

1. exige `main`, environment `production` y confirmación explícita;
2. crea y espera un snapshot manual de RDS;
3. invoca el payload
   `{"import_consent_templates":"dry-run","consent_template_catalog":"fase6"}`;
4. exige exactamente 19 versiones aprobadas;
5. ejecuta el apply idempotente;
6. invoca `{"verify":"biblioteca_normativa"}`.

El verificador compara los 19 hashes inmutables, confirma que son las versiones
publicadas y comprueba su tipo documental. Las cuatro plantillas estéticas existentes no
se retiran; después del rollout habrá 23 identidades de plantilla y una sola versión
publicada por identidad.

## Referencias de trabajo

Los borradores se orientaron con fuentes oficiales vigentes consultadas el 16 de julio de
2026: NOM-004-SSA3-2012; NOM-012-SSA3-2012; Ley General de Salud (última reforma indicada
por la Cámara de Diputados: 15-01-2026); Reglamento de la Ley General de Salud en materia
de prestación de servicios de atención médica; y Ley Federal de Protección de Datos
Personales en Posesión de los Particulares (reforma indicada: 14-11-2025).

Estas referencias no equivalen a dictamen. Las plantillas de trasplantes, investigación,
necropsia y salud reproductiva requieren revisión por profesionales con competencia
específica, además de la revisión jurídica sanitaria.

## Criterios de aceptación

- Paquete técnico de 19 documentos: implementado.
- Firmantes y hasta dos testigos configurables: implementado sobre el motor Fase 4–5.
- Versionado e importación sin infraestructura nueva: implementado.
- Distinción de tipos documentales: implementada y verificada.
- Aprobación clínica y jurídica real: pendiente de los profesionales responsables; la
  publicación está bloqueada hasta completarla.
