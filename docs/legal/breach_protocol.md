# Protocolo de Respuesta a Brecha de Datos

> **Documento interno. No compartir con pacientes ni terceros.**  
> **LFPDPPP: notificación en máximo 72 horas al titular afectado.**

---

## 1. Detección e Identificación

### Señales de alerta
- Accesos inusuales en `audit_log` (horarios atípicos, IPs desconocidas)
- Alertas de AWS GuardDuty o CloudTrail
- Reportes de usuarios sobre accesos no autorizados
- Alertas de WAF por volumen inusual de requests bloqueados

### Pasos inmediatos (Hora 0-1)
1. **Confirmar** que la brecha es real (no un falso positivo)
2. **Documentar** la hora de detección, quién la detectó, y evidencia inicial
3. **Notificar** al responsable técnico y al responsable legal
4. **Preservar evidencia:** NO eliminar logs, NO reiniciar servicios hasta documentar

---

## 2. Contención (Hora 1-4)

### Acciones técnicas
- [ ] Revocar credenciales comprometidas (Cognito: deshabilitar usuario, rotar tokens)
- [ ] Rotar secretos en Secrets Manager si las credenciales de BD fueron expuestas
- [ ] Bloquear IPs sospechosas en WAF
- [ ] Si hay acceso no autorizado activo: deshabilitar el API Gateway temporalmente
- [ ] Rotar la llave de firma ECDSA si fue comprometida (crear nueva, actualizar alias)

### Preservación de evidencia
- [ ] Exportar logs de CloudTrail del período del incidente
- [ ] Exportar registros de `audit_log` del período afectado
- [ ] Tomar snapshot de la base de datos Aurora
- [ ] Documentar toda acción de contención con timestamps

---

## 3. Evaluación de Impacto (Hora 4-24)

### Determinar alcance
- ¿Cuántos pacientes fueron afectados?
- ¿Qué datos fueron accedidos/exfiltrados?
- ¿Fueron datos sensibles (información clínica)?
- ¿Los datos estaban cifrados al momento del acceso?
- ¿Qué tenants (médicos) están afectados?

### Documentar
- Tipo de brecha (acceso no autorizado, exfiltración, ransomware, error humano)
- Vector de ataque (credenciales robadas, vulnerabilidad, ingeniería social)
- Datos expuestos (categoría y volumen)
- Sistemas afectados

---

## 4. Notificación (Hora 24-72)

### LFPDPPP — Notificación al titular (paciente)

**Plazo máximo: 72 horas desde la detección.**

La notificación debe incluir:
1. Naturaleza del incidente
2. Datos personales comprometidos
3. Recomendaciones al titular para proteger sus intereses
4. Acciones correctivas implementadas
5. Medios de contacto para más información

### Template de notificación al paciente

```
Estimado/a [NOMBRE_PACIENTE]:

Le informamos que el [FECHA] detectamos un incidente de seguridad 
que pudo haber afectado la confidencialidad de sus datos personales 
almacenados en nuestro sistema de expediente clínico electrónico.

Datos potencialmente afectados: [DESCRIPCIÓN]

Acciones tomadas:
- [ACCIONES DE CONTENCIÓN]
- [ACCIONES DE REMEDIACIÓN]

Recomendaciones:
- [RECOMENDACIONES AL PACIENTE]

Para más información o para ejercer sus derechos ARCO, contacte:
privacidad@medrecord.mx

Atentamente,
[NOMBRE_RESPONSABLE]
```

### INAI — Notificación al regulador (si aplica)

Si la brecha involucra datos sensibles de salud, notificar al INAI:
- Portal: https://home.inai.org.mx
- Incluir: descripción del incidente, datos afectados, medidas tomadas, cantidad de titulares afectados

---

## 5. Remediación (Día 3-14)

- [ ] Implementar correcciones técnicas para cerrar el vector de ataque
- [ ] Auditoría completa de accesos en el período del incidente
- [ ] Actualizar políticas de seguridad si es necesario
- [ ] Capacitar al equipo sobre las lecciones aprendidas
- [ ] Actualizar este protocolo con las lecciones del incidente

---

## 6. Post-Mortem (Día 14-30)

- [ ] Documento de post-mortem con causa raíz
- [ ] Acciones preventivas para evitar recurrencia
- [ ] Revisión de controles de seguridad
- [ ] Actualizar la evaluación de riesgos
- [ ] Comunicar resultados al equipo

---

## Contactos de Emergencia

| Rol | Nombre | Contacto |
|---|---|---|
| Responsable técnico | [NOMBRE] | [EMAIL/TEL] |
| Responsable legal | [NOMBRE] | [EMAIL/TEL] |
| AWS Support | N/A | Consola AWS → Support |
| INAI | N/A | https://home.inai.org.mx |
