#!/bin/bash
# scripts/audit.sh
# Consultar registros de auditoría inmutables desde AWS CloudWatch.
# Uso: ./scripts/audit.sh [correo@doctor.com] [tiempo] (ej. 10m, 2h, 1d)

EMAIL=${1}
SINCE=${2:-"1h"}

if [[ -z "$EMAIL" ]]; then
  echo "Uso: ./scripts/audit.sh <correo> [tiempo]"
  echo "Ejemplo: ./scripts/audit.sh doctor@ejemplo.com 24h"
  exit 1
fi

echo "🔍 Consultando logs de auditoría para $EMAIL (últimas $SINCE)..."

if command -v jq &> /dev/null; then
  aws logs tail /aws/lambda/medrecord-api-prod --since "$SINCE" --format short | \
    grep -Eo '\{"request_id":.*"exito":.*\}' | \
    grep "\"$EMAIL\"" | \
    jq -r '"[\(.timestamp[0:19])] \(.method) \(.path) | IP: \(.ip_origen) | Éxito: \(.exito) | Tiempo: \(.duration_ms)ms"'
else
  aws logs tail /aws/lambda/medrecord-api-prod --since "$SINCE" --format short | \
    grep -Eo '\{"request_id":.*"exito":.*\}' | \
    grep "\"$EMAIL\""
fi
