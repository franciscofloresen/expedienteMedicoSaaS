#!/bin/bash
# scripts/audit.sh

EMAIL=${1}
SINCE=${2:-"1h"}

if [[ -z "$EMAIL" ]]; then
  echo "Uso: ./scripts/audit.sh <correo> [tiempo]"
  exit 1
fi

echo "🔍 Consultando logs de auditoría para $EMAIL (últimas $SINCE)..."

function parse_logs() {
  # 1. grep -o '{.*}' extrae el JSON principal que envuelve al mensaje
  # 2. jq parsea ese JSON, extrae el string interno ".message", lo convierte a JSON con fromjson, filtra por correo y formatea.
  grep -o '{.*}' | \
  jq -r --arg email "$EMAIL" '
    select(.name == "medrecord.audit" and .message != null) | 
    .message | 
    fromjson | 
    select(.user_email == $email) | 
    "[\(.timestamp[0:19]) UTC] \(.method) \(.path) | IP: \(.ip_origen) | Éxito: \(.exito) | Tiempo: \(.duration_ms)ms"
  '
}

if [[ -f "backend/local_audit.log" ]]; then
  echo "📂 Leyendo de archivo local (backend/local_audit.log)..."
  cat backend/local_audit.log | parse_logs
else
  echo "☁️  Leyendo desde AWS CloudWatch..."
  OUTPUT=$(aws logs tail /aws/lambda/medrecord-api-prod --since "$SINCE" --format short 2>/dev/null | parse_logs)
  
  if [[ -z "$OUTPUT" ]]; then
    echo "❌ No se encontraron logs para ese correo en AWS (o no tienes sesión iniciada en AWS CLI)."
  else
    echo "$OUTPUT"
  fi
fi
