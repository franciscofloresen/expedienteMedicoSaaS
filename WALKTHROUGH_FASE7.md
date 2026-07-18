# Walkthrough — Fase 7: paquete de dermatología y medicina estética

## Resultado

La primera entrega continua de Fase 7 incorpora un paquete candidato de 10
consentimientos de dermatología/medicina estética. No agrega migraciones ni recursos AWS:
reutiliza el catálogo global, el versionado inmutable, las firmas, el PDF final, la
revocación y la operación administrativa construidos en Fases 4–6.

El alcance corresponde al primer paquete del roadmap:

1. Toxina botulínica.
2. Relleno con ácido hialurónico.
3. Peeling químico.
4. Láser o luz intensa pulsada.
5. Microneedling.
6. Plasma rico en plaquetas.
7. Biopsia de piel.
8. Escisión de lesión cutánea.
9. Crioterapia.
10. Procedimiento dermatológico/estético no quirúrgico general.

El formato general es deliberadamente un respaldo: el propio texto prohíbe usarlo cuando
exista una carta específica y obliga a identificar producto o equipo, registro,
parámetros, zonas, sesiones y riesgos propios.

## Artefactos y compuerta

- `backend/app/data/consent_templates_phase7_dermatology.json`: 10 versiones candidatas,
  todas clasificadas como `consentimiento_informado` y especialidad
  `Dermatología y medicina estética`.
- `backend/app/data/consent_template_reviews_phase7_dermatology.json`: manifiesto de doble
  revisión por `template_key` y versión.
- `backend/app/services/consent_template_reviews.py`: compuerta generalizada por paquete,
  conservando la compatibilidad y las 19 identidades exactas de Fase 6.

Cada documento sigue marcado `BORRADOR`, sin responsable ni fecha inventados. Para poder
publicarse necesita:

- aprobación clínica nominativa de un profesional competente, con rol o cédula, fecha y
  evidencia;
- aprobación jurídica sanitaria nominativa con los mismos elementos;
- retiro del aviso de borrador y consolidación de ambos responsables y la fecha más
  reciente dentro del artefacto que quedará sellado por hash.

Mientras falte cualquiera de esos elementos, tanto `dry-run` como `apply` devuelven
`ok=false` antes de abrir una sesión de PostgreSQL.

## Contenido y referencias de seguridad

El texto candidato obliga a individualizar producto, lote, dispositivo, técnica, zona,
parámetros y riesgos. Se hizo explícita la urgencia de la oclusión vascular en rellenos,
la propagación sistémica de toxina, la protección ocular en láser, la diferencia de
riesgo de microneedling con radiofrecuencia, el manejo de muestras de patología y la
ausencia de muestra histológica en crioterapia.

Las fuentes de trabajo verificadas el 17 de julio de 2026 incluyen:

- NOM-004-SSA3-2012 y el Reglamento de la Ley General de Salud en materia de prestación
  de servicios de atención médica;
- guía COFEPRIS 2025 para establecimientos de atención médica con fines estéticos no
  quirúrgicos y la alerta sobre sustancias modelantes;
- referencias clínicas oficiales FDA sobre rellenos dérmicos, toxina botulínica y
  dispositivos de microneedling, incluida la comunicación de seguridad de radiofrecuencia
  de 2025;
- registro sanitario e instructivo de uso de cada producto o dispositivo, que el revisor
  deberá validar contra los insumos que realmente ofrezca el consultorio.

Estas fuentes orientan el borrador; no sustituyen el dictamen profesional ni permiten
marcar una revisión como aprobada.

## Herramienta local y operación

```bash
cd backend
python -m scripts.consent_template_tool validate \
  app/data/consent_templates_phase7_dermatology.json
python -m scripts.consent_template_tool preview dermatologia_relleno_acido_hialuronico \
  --path app/data/consent_templates_phase7_dermatology.json
python -m scripts.consent_template_tool review-status --catalog fase7_dermatologia
```

`review-status` termina con código 1 mientras haya revisiones pendientes. Una vez
completadas las 10 clínicas y 10 jurídicas debe terminar con código 0.

El workflow `Ops — Consent Templates (Production)` acepta
`catalog=fase7_dermatologia`:

1. exige `main`, environment `production` y confirmación explícita;
2. crea y espera un snapshot manual de RDS;
3. invoca el dry-run y exige exactamente 10 versiones aprobadas;
4. ejecuta el apply idempotente;
5. invoca `verify=paquete_dermatologia`.

El verificador compara los 10 hashes inmutables publicados y confirma que la metadata de
especialidad no se desvió. También está disponible en `Ops — Verify` como verificación
read-only posterior.

## Criterios de aceptación

- [x] Diez identidades exactas del primer paquete del roadmap.
- [x] Contenido candidato por procedimiento con campos y riesgos individualizables.
- [x] Compuerta de doble revisión que falla antes de acceder a la base de datos.
- [x] Importador y workflow con conteo exacto, snapshot, idempotencia y verificación.
- [x] Verificador read-only registrado para producción.
- [x] Cero migraciones y cero infraestructura AWS nueva.
- [ ] Diez aprobaciones clínicas reales documentadas.
- [ ] Diez aprobaciones jurídicas sanitarias reales documentadas.
- [ ] Publicación y verificación ejecutadas en producción.

La Fase 7 es continua: este walkthrough cierra la implementación técnica del primer
paquete, no autoriza a construir los siguientes. Cirugía menor, odontología y demás
especialidades se priorizan sólo con demanda observada.
