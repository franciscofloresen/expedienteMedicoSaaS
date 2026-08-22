import { Link } from 'react-router-dom';
import { ShieldCheck, ArrowLeft } from 'lucide-react';

export default function Privacidad() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg-app)', display: 'flex', flexDirection: 'column' }}>
      {/* Navbar Simple */}
      <nav style={{ padding: '1.25rem 5%', backgroundColor: 'var(--bg-card)', borderBottom: '1px solid var(--border-light)' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', color: 'var(--text-muted)', fontWeight: 500 }}>
          <ArrowLeft size={20} /> Volver al Inicio
        </Link>
      </nav>

      <main style={{ flex: 1, padding: '4rem 5%' }}>
        <article style={{ maxWidth: '800px', margin: '0 auto', backgroundColor: 'var(--bg-card)', padding: '4rem', borderRadius: '24px', boxShadow: 'var(--shadow-sm)' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
            <div style={{ background: 'rgba(0, 122, 255, 0.1)', padding: '0.75rem', borderRadius: '12px', color: 'var(--primary)' }}>
              <ShieldCheck size={32} />
            </div>
            <div>
              <h1 style={{ fontSize: '2rem', margin: 0, fontWeight: 700, letterSpacing: '-0.02em' }}>Privacidad y Términos Legales</h1>
              <p style={{ margin: 0, color: 'var(--text-muted)' }}>Última actualización: Agosto de 2026</p>
            </div>
          </div>

          <div style={{ color: 'var(--text-main)', lineHeight: 1.8, fontSize: '1.05rem' }}>
            <p>
              Bienvenido a <strong>CloudMedRecord</strong>. Al utilizar nuestra plataforma, usted (en adelante "El Médico", "La Clínica" o "El Usuario") acepta los presentes Términos de Servicio y el Aviso de Privacidad. Este documento rige nuestra relación legal y técnica, y está diseñado para cumplir estrictamente con la legislación mexicana vigente.
            </p>

            <hr style={{ margin: '3rem 0', borderColor: 'var(--border-light)' }} />

            <h2 style={{ fontSize: '1.6rem', color: 'var(--primary)', marginBottom: '1rem' }}>Términos de Servicio (B2B)</h2>
            
            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>1. Naturaleza del Servicio y Modelo de Responsabilidad Compartida</h3>
            <p>
              CloudMedRecord proporciona software como servicio (SaaS) para la gestión de expedientes clínicos electrónicos. Para efectos de la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP), <strong>El Médico o La Clínica actúa como el "Responsable"</strong> de los datos personales y sensibles de los pacientes. <strong>CloudMedRecord actúa exclusivamente como el "Encargado"</strong> del tratamiento, prestando infraestructura tecnológica y almacenamiento.
            </p>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>2. Infraestructura en la Nube, Cifrado e Integridad</h3>
            <p>
              El Médico autoriza expresamente a CloudMedRecord a utilizar proveedores de infraestructura en la nube (PaaS/IaaS) con certificaciones internacionales (ej. ISO 27001, SOC 2). La información se transmite cifrada en tránsito (TLS) y se almacena cifrada en reposo mediante llaves administradas en AWS KMS, tanto en la base de datos como en los archivos y documentos.
            </p>
            <p>
              Adicionalmente, el domicilio del paciente y los antecedentes del expediente se cifran a nivel de aplicación con una llave dedicada y quedan vinculados criptográficamente al consultorio que los generó.
            </p>
            <p>
              El resto del contenido clínico —notas de evolución, recetas y consentimientos— se almacena cifrado en reposo y protegido por aislamiento estricto entre consultorios a nivel de base de datos. Al no estar cifrado a nivel de aplicación, el personal de CloudMedRecord con acceso administrativo a la base de datos tiene la capacidad técnica de leerlo. Frente a esa capacidad, <strong>CloudMedRecord se obliga a no acceder al contenido clínico</strong>, salvo (a) instrucción expresa y documentada del Médico, (b) necesidad demostrable de reparar una falla que afecte a ese expediente, o (c) mandato de autoridad competente; todo acceso de esa naturaleza queda registrado y a disposición del Médico. El personal está sujeto a una obligación de confidencialidad que subsiste al término de la relación.
            </p>
            <p>
              CloudMedRecord <strong>no habilita la suplantación de identidad del Médico desde soporte</strong>: el sistema rechaza activamente los tokens de sesión que la indican.
            </p>
            <p>
              La integridad de los documentos firmados no depende de la confidencialidad: cada nota, receta y consentimiento firmado lleva una huella SHA-256 y una firma electrónica cuya llave privada no sale de AWS KMS, y cualquier alteración posterior es detectable de forma independiente por el Médico o por un tercero.
            </p>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>3. Cumplimiento de la NOM-004 y NOM-024</h3>
            <p>
              CloudMedRecord garantiza la existencia de una bitácora de auditoría inalterable que registra accesos, modificaciones y eliminaciones, cumpliendo con los requisitos de trazabilidad estipulados en la NOM-024-SSA3-2012. Asimismo, la plataforma facilita la retención de registros médicos por el periodo obligatorio de 5 años (NOM-004-SSA3-2012).
            </p>

            <hr style={{ margin: '3rem 0', borderColor: 'var(--border-light)' }} />

            <h2 style={{ fontSize: '1.6rem', color: 'var(--primary)', marginBottom: '1rem' }}>Aviso de Privacidad</h2>

            <p>
              En cumplimiento con la <strong>LFPDPPP</strong> y su Reglamento, hacemos de su conocimiento nuestra política de privacidad:
            </p>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>1. Datos Personales Recabados</h3>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}>
              <li><strong>Del Médico (Usuarios de la Plataforma):</strong> Nombre completo, Cédula Profesional, Especialidad, Correo Electrónico (utilizado para el acceso a la cuenta y el envío de notificaciones de servicio).</li>
              <li><strong>De los Pacientes (Recabados por el Responsable):</strong> Datos de identificación, datos de contacto, y <strong>Datos Sensibles</strong> consistentes en el historial clínico, diagnósticos y notas de evolución.</li>
            </ul>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>2. Finalidad del Tratamiento</h3>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}>
              <li><strong>Finalidad Principal:</strong> Proveer, mantener y operar el expediente clínico electrónico para facilitar la atención médica brindada por el Médico tratante.</li>
              <li><strong>Notificaciones de Servicio (Finalidad Principal):</strong> Enviar a la dirección de correo electrónico registrada por el Médico avisos transaccionales inherentes a la operación de su cuenta, tales como confirmaciones de creación, actualización o cancelación de citas. Al ser comunicaciones necesarias para la prestación del servicio, no requieren consentimiento adicional y no constituyen publicidad.</li>
              <li><strong>Finalidad Secundaria:</strong> Estadísticas de uso anonimizadas para mejorar el rendimiento del software. (Nunca aplicable a datos sensibles del paciente).</li>
            </ul>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>3. Transferencia de Datos</h3>
            <p>
              CloudMedRecord no vende ni comercializa datos personales o sensibles. Los datos se transmiten mediante protocolos de cifrado en tránsito (TLS/SSL) y se procesan en infraestructura de Amazon Web Services (AWS), que puede ubicarse en Estados Unidos. Para el envío de notificaciones de servicio, CloudMedRecord utiliza Amazon Simple Email Service (Amazon SES) en calidad de encargado. Dichas notificaciones se entregan a la dirección de correo electrónico proporcionada por el Médico, la cual es administrada por el propio Médico o por su proveedor de correo; el Médico es responsable de mantener la seguridad y confidencialidad de dicha cuenta. Con el fin de proteger los datos sensibles de los pacientes, las notificaciones se limitan a la información mínima necesaria (título, fecha y estado de la cita) y <strong>no incluyen notas clínicas</strong>.
            </p>

            <h3 style={{ fontSize: '1.2rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>4. Derechos ARCO</h3>
            <p>
              Tanto Médicos como Pacientes conservan sus derechos de <strong>Acceso, Rectificación, Cancelación y Oposición</strong>. Los pacientes deberán ejercer sus derechos ARCO directamente ante su Médico Tratante (El Responsable). CloudMedRecord brindará al Médico las herramientas tecnológicas para procesar dichas solicitudes. Cabe recalcar que el derecho de Cancelación de datos de salud está condicionado a los plazos obligatorios de retención médica marcados por la Secretaría de Salud.
            </p>

            <div style={{ marginTop: '3rem', padding: '1.5rem', backgroundColor: 'var(--bg-app)', borderRadius: '12px', border: '1px solid var(--border-light)' }}>
              <p style={{ margin: 0, fontSize: '0.95rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                Si tiene dudas sobre el tratamiento de sus datos o estos términos, por favor contacte al oficial de privacidad de CloudMedRecord.
              </p>
            </div>

          </div>
        </article>
      </main>
    </div>
  );
}
