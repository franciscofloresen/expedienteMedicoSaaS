# Empaquetado seguro de Lambda

## Objetivo

El backend se distribuye como un ZIP reproducible y verificado. Como no existe un
entorno de *staging*, CI construye e importa el mismo artefacto de producción antes
de permitir el despliegue.

## Qué entra al artefacto

- Las dependencias normales de `backend/pyproject.toml` son exclusivamente de
  ejecución. Las herramientas locales y `uvicorn[standard]` están en el extra
  `dev` y no se instalan en Lambda.
- `backend/lambda-constraints.txt`, generado desde `uv.lock`, fija todas las
  versiones transitivas del runtime. Así CI y CD no resuelven árboles diferentes
  para el mismo commit.
- Se incluyen `app/`, `alembic/`, `alembic.ini` y únicamente los scripts listados
  en `RUNTIME_SCRIPT_FILES` de `backend/scripts/build_lambda_package.py`.
- Se eliminan cachés de Python, pruebas internas de dependencias y ejecutables de
  consola. Los datos y módulos de botocore se conservan completos porque algunos
  clientes y *waiters* los importan en ejecución.
- Se conservan boto3/botocore, ReportLab, Pillow y cryptography: son dependencias
  reales de producción y quitarlas o fragmentarlas pondría en riesgo integraciones
  AWS, consentimientos y firmas.

Los scripts de semillas, herramientas locales, smoke tests y operaciones
destructivas no se publican dentro de la función. Para agregar un nuevo evento
operativo de Lambda hay que añadir explícitamente su módulo a `RUNTIME_SCRIPT_FILES`
y `REQUIRED_MODULES`, junto con una prueba.

Cuando cambien dependencias de producción, se actualizan ambos archivos:

```bash
uv lock
uv export --frozen --no-dev --no-emit-project --no-hashes \
  --no-annotate --no-header > lambda-constraints.txt
```

## Límites y controles

El empaquetador falla por encima de 225 MiB sin comprimir, dejando 25 MiB de margen
frente al límite de AWS de 250 MiB. Advierte cuando el ZIP pasa 45 MiB. El flujo no
depende del límite de carga directa de 50 MiB: sube el ZIP cifrado con SSE-S3 al
bucket privado `medrecord-lambda-artifacts-prod-<account>` y despliega Lambda desde
S3.

Cada objeto usa una ruta ligada al SHA del release, se elimina al terminar el job y
una regla de ciclo de vida lo expira en un día si la limpieza no llega a ejecutarse.
El bucket bloquea acceso público y tráfico sin TLS.

## Validación local

Desde `backend/`:

```bash
python scripts/build_lambda_package.py \
  --package-dir /tmp/lambda-package \
  --zip-path /tmp/backend.zip \
  --manifest-path /tmp/lambda-package-manifest.json
```

El manifiesto muestra los tamaños comprimido/sin comprimir, los componentes más
pesados y el allowlist de scripts. Además, el proceso abre un intérprete aislado e
importa todos los módulos requeridos usando sólo el contenido empaquetado.

## Despliegue y recuperación

Terraform crea primero el bucket y sus permisos mínimos. Después, el job del backend
sube el ZIP, publica una nueva versión de Lambda, espera a que termine la actualización
y ejecuta migraciones, verificadores clínicos y el smoke test existente. El cambio de
empaquetado no modifica el esquema de base de datos.

Si falla la construcción o cualquier importación, no se toca Lambda. Si falla una
verificación posterior al cambio de código, se debe revertir el commit en `main` y
relanzar el flujo; el frontend permanece en el mecanismo de mantenimiento/restauración
ya definido por el pipeline.

No se usa una Lambda Layer: las capas también cuentan contra el límite total
descomprimido de 250 MiB y añadirían una segunda unidad que versionar y validar sin
reducir el peso efectivo.
