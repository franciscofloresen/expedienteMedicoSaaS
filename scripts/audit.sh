#!/bin/bash
# scripts/audit.sh
# Consultar registros de auditoría inmutables desde AWS CloudWatch.
# Uso: ./scripts/audit.sh [tiempo] (ej. 10m, 2h, 1d)

SINCE=${1:-"1h"}
echo "🔍 Consultando logs de auditoría (CloudWatch) de las últimas $SINCE..."

if command -v jq &> /dev/null; then
  aws logs tail /aws/lambda/medrecord-api-prod --since "$SINCE" --format short | \
    grep -Eo '\{"request_id":.*"exito":.*\}' | \
    jq -r '"[\(.timestamp | substr(0;19))] \(.method) \(.path) | IP: \(.ip_origen) | Éxito: \(.exito) | Tiempo: \(.duration_ms)ms"'
else
  aws logs tail /aws/lambda/medrecord-api-prod --since "$SINCE" --format short | grep -Eo '\{"request_id":.*"exito":.*\}'
fi
