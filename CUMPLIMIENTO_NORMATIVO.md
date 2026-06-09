# Guía de Cumplimiento Normativo y Legal
**Sistema de Expediente Clínico Electrónico (ECE)**

Este documento describe las normativas legales que rigen el tratamiento de la información médica en México y cómo este sistema aborda y cumple técnica y arquitectónicamente con dichos requerimientos. 

Esta documentación es vital para procesos de auditoría, inversión (Due Diligence) y certificación frente a autoridades (COFEPRIS, DGIS, INAI).

---

## 1. NOM-004-SSA3-2012 — Del Expediente Clínico
*Regula cómo debe integrarse, manejarse, conservarse y estructurarse la información del expediente clínico, ya sea en papel o formato electrónico.*

### Requisitos Funcionales y Técnicos en el Sistema
* **Conservación Obligatoria (5 Años):** Los expedientes clínicos son propiedad del prestador de servicios médicos, pero los datos son del paciente. Por ley, deben conservarse por un mínimo de **5 años** a partir de la fecha del último acto médico.
  * *Solución Técnica:* Implementación estricta de "Soft Delete" (Eliminación Lógica). La base de datos NUNCA elimina registros de pacientes ni notas médicas; simplemente se marcan como inactivos o archivados (`activo = false`).
* **Estructura Clínica Estricta:** Debe contener ficha de identificación, antecedentes, historia clínica, notas de evolución e interconsultas.
  * *Solución Técnica:* Validación de campos obligatorios en el modelo de datos (Demografía, AHF, APP, etc.) y estructuras predefinidas para Notas de Evolución (Signos vitales obligatorios, Diagnóstico y Plan).
* **Autoría Inequívoca:** Toda nota médica debe tener fecha, hora y nombre de quien la elabora.
  * *Solución Técnica:* Relación inquebrantable a nivel de Base de Datos entre el registro de la nota y el `usuario_id` del médico (JWT validado), estampando un `timestamp` generado por el servidor, no por el cliente.

---

## 2. NOM-024-SSA3-2012 — Sistemas de Información de Registro Electrónico para la Salud (SIRES)
*Garantiza la interoperabilidad, procesamiento, interpretación, confidencialidad, seguridad y uso de estándares en los expedientes electrónicos.*

### Requisitos Funcionales y Técnicos en el Sistema
* **Inmutabilidad y Firma Electrónica:** Las notas médicas finalizadas no deben poder modificarse ("tachaduras o enmendaduras"). Toda corrección debe hacerse mediante una "Nota Aclaratoria".
  * *Solución Técnica:* Botón de "Firma Digital Criptográfica". Al firmar una nota, se bloquea su edición a nivel de Base de Datos, se sella con un Timestamp y se genera un hash de integridad. Solo se permiten leer o imprimir, pero nunca editar.
* **Trazabilidad y Auditoría (Audit Trail):** El sistema debe registrar de forma automática, silenciosa e inalterable cada acción.
  * *Solución Técnica:* Middleware de Auditoría global. Registra cada método HTTP (GET, POST, DELETE), la ruta, el ID del paciente visualizado, el usuario y la dirección IP. El log de auditoría está aislado y el usuario no puede borrarlo.
* **Control de Accesos Basado en Roles (RBAC):** Privacidad por diseño.
  * *Solución Técnica:* Sistema Multitenant (Aislamiento de Bases de Datos por RLS). Un médico de la Clínica A jamás podrá acceder, consultar ni ver métricas de la Clínica B. Adicionalmente, roles internos (Médico vs Asistente).

---

## 3. Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP)
*Regula el tratamiento de los datos para garantizar la privacidad y el derecho a la autodeterminación informativa.* **Atención: Los datos médicos están catalogados legalmente como "Datos Sensibles".**

### Requisitos Funcionales y Técnicos en el Sistema
* **Consentimiento Expreso:** El tratamiento de datos de salud requiere el consentimiento explícito del titular.
  * *Solución Técnica:* Módulo de "Privacidad y NOM-024" integrado en el expediente. Requiere que el paciente declare haber leído el Aviso de Privacidad y el médico presione el botón de "Registrar Consentimiento", estampando el evento irreversiblemente en la tabla de Auditoría como prueba jurídica.
* **Seguridad Criptográfica (Datos en Tránsito y Reposo):**
  * *Solución Técnica:* Los datos deben transmitirse obligatoriamente por TLS/HTTPS. En bases de datos de producción (AWS RDS / PostgreSQL), los volúmenes están cifrados mediante AWS KMS.
* **Derechos ARCO (Especialmente Acceso y Rectificación):**
  * *Solución Técnica:* Se otorga al médico la herramienta de "Imprimir Reporte Técnico" y "Exportar Expediente" para poder entregar rápidamente copias al paciente si ejerce su derecho de Acceso. (El derecho de Cancelación está supeditado a los 5 años de la NOM-004).

---

## 4. Decreto de Digitalización del Sector Salud (Enero 2026)
*Iniciativa gubernamental para modernizar la salud digital en México, buscando la eliminación de expedientes fragmentados y la creación de un sistema interconectado nacional.*

### Requisitos Funcionales y Técnicos en el Sistema
* **La CURP como Llave Primaria de Identidad Universal:** Se elimina la dependencia exclusiva de los números de folio internos.
  * *Solución Técnica:* El sistema ya solicita y gestiona la CURP. El modelo de datos está preparado para validar el formato de 18 caracteres alfanuméricos.
* **Portabilidad del Expediente (El paciente es dueño de su información):** El paciente podrá decidir cambiar de clínica y llevarse su expediente en un "USB virtual" u otorgar permisos de consulta.
  * *Solución Técnica:* Al estar el backend construido en **FastAPI (Python)** mediante RESTful APIs (y preparado para JSON), exportar la data clínica bajo el estándar **HL7 FHIR** o en archivos de intercambio estructurados será una actualización de bajo esfuerzo frente a sistemas Legacy (Sistemas antiguos en papel o monolíticos).
* **Interoperabilidad Gubernamental (APIs Abiertas):**
  * *Solución Técnica:* La arquitectura separada (Frontend SPA en React y Backend API de micro-servicios en FastAPI) permite que mañana se puedan enchufar las APIs directas de la Secretaría de Salud para validar certificados de defunción, recetas electrónicas o reportes epidemiológicos automáticos sin romper la interfaz gráfica del usuario.
