# Perspectiva Startup: Preocupaciones y Análisis del Plan

## El Problema de Fondo
Este plan convierte un proyecto de **12 semanas en 16-24 semanas**, y lo hace antes de tener un solo médico pagando. Eso es exactamente lo opuesto a lo que hablamos antes.

---

## Decisiones Estratégicas para el MVP (Cierres Inmediatos)

Estas 4 decisiones deben quedar cerradas antes de escribir la primera línea de código para mitigar riesgos:

### Decisión 1 — Firma Digital
* **Estrategia:** KMS ECDSA por tenant, pero aplicando la optimización de una **sola llave compartida con Key Context** para evitar costos absurdos.
* **Exclusión:** **No se usará WebAuthn para el MVP**. Agrega demasiada fricción en la experiencia de usuario (UX) y complejidad de implementación para una acción que el médico realizará docenas de veces al día.

### Decisión 2 — Región de Despliegue
* **Estrategia:** **us-east-1** como región primaria es lo correcto (no existe región de AWS en México).
* **Exclusión:** **No se implementará DR (Disaster Recovery) multi-región para el MVP**. Es un lujo innecesario en esta etapa; se moverá al roadmap para cuando se alcancen los 100+ médicos de pago.

### Decisión 3 — Timeline de Desarrollo
* **Estrategia:** Si el desarrollo depende de una sola persona, un plan de 24 semanas antes de lanzar es inviable para una startup. 
* **Meta:** El camino correcto es recortar el alcance a **8-10 semanas hasta tener un MVP funcional** (aunque sea limitado) e iterar de inmediato con usuarios reales.

### Decisión 4 — Facturación (CFDI)
* **Exclusión:** **No se incluirá CFDI en el MVP**. Representa una complejidad legal y técnica considerable en etapas tempranas. Ningún médico rechazará el producto porque no genere facturas el primer mes; sin embargo, sí lo rechazarán si el expediente clínico es lento o difícil de usar.

---

## Puntos Críticos de Infraestructura y Costos

### 1. KMS Signing Keys (Problema de Escalabilidad)
* **El problema:** Son un problema de escalabilidad costoso y mal resuelto. A **$1 USD/key/mes**, con 500 médicos pagaríamos **$500 USD/mes** solo en llaves de firma.
* **La alternativa del plan:** El plan sugiere cambiar a *CloudHSM* al superar los 1,000 usuarios, pero cuesta **$1,150 USD/mes**. 
* **Impacto financiero:** Para un SaaS con una tarifa de **$499 MXN/médico**, esto es un problema estructural de diseño que se debe resolver desde la arquitectura, no parcharlo después.

### 2. Provisioned Concurrency (Prematuro)
* **El problema:** El plan propone un gasto de **$38 USD/mes desde el MVP**.
* **Análisis:** Con solo 50 médicos operando en un horario laboral normal, los *cold starts* de Lambda (~300ms) son completamente aceptables. Este costo solo se justifica con quejas reales de latencia.

### 3. Cross-region DR (Prematuro)
* **El problema:** Añade complejidad operacional y costos reales antes de tener ingresos que proteger.
* **Cumplimiento:** El backup de 35 días con **PITR (Point-in-Time Recovery) de Aurora** ya es suficiente para cumplir con la NOM legalmente.