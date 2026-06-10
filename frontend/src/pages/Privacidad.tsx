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
              <h1 style={{ fontSize: '2rem', margin: 0, fontWeight: 700, letterSpacing: '-0.02em' }}>Aviso de Privacidad</h1>
              <p style={{ margin: 0, color: 'var(--text-muted)' }}>Última actualización: Junio de 2026</p>
            </div>
          </div>

          <div style={{ color: 'var(--text-main)', lineHeight: 1.8, fontSize: '1.1rem' }}>
            <p>
              En cumplimiento con la <strong>Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP)</strong> y su Reglamento, así como las normativas aplicables en materia de salud en México (NOM-004-SSA3-2012 y NOM-024-SSA3-2012), <strong>MedRecord</strong>, pone a su disposición el presente Aviso de Privacidad.
            </p>

            <h2 style={{ fontSize: '1.4rem', marginTop: '2.5rem', marginBottom: '1rem' }}>1. Datos Personales que Recabamos</h2>
            <p>
              Para llevar a cabo las finalidades descritas en el presente aviso, recabaremos los siguientes datos personales:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}>
              <li>Datos de identificación (Nombre, CURP, Edad).</li>
              <li>Datos de contacto (Correo electrónico, Teléfono).</li>
              <li><strong>Datos Sensibles:</strong> Historial clínico, diagnósticos, recetas, notas de evolución y cualquier información biomédica registrada por su médico tratante.</li>
            </ul>

            <h2 style={{ fontSize: '1.4rem', marginTop: '2.5rem', marginBottom: '1rem' }}>2. Finalidad del Tratamiento</h2>
            <p>
              Sus datos personales sensibles serán utilizados exclusiva y estrictamente para:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem' }}>
              <li>Integrar y mantener su Expediente Clínico Electrónico.</li>
              <li>Facilitar la consulta y diagnóstico por parte de su médico tratante.</li>
              <li>Cumplir con las obligaciones legales establecidas por la Secretaría de Salud.</li>
            </ul>

            <h2 style={{ fontSize: '1.4rem', marginTop: '2.5rem', marginBottom: '1rem' }}>3. Seguridad y Resguardo (Auditoría Inmutable)</h2>
            <p>
              Nos comprometemos a que los datos serán tratados bajo estrictas medidas de seguridad. El sistema <strong>MedRecord</strong> utiliza firmas digitales criptográficas (Sello de Inmutabilidad) en todas las notas médicas para garantizar que no puedan ser alteradas una vez guardadas, asegurando integridad total. Además, toda visualización de su expediente queda registrada en una <strong>Bitácora de Auditoría</strong>, visible para el administrador de la clínica.
            </p>

            <h2 style={{ fontSize: '1.4rem', marginTop: '2.5rem', marginBottom: '1rem' }}>4. Derechos ARCO</h2>
            <p>
              Usted tiene derecho a conocer qué datos personales tenemos de usted, para qué los utilizamos y las condiciones de su uso (<strong>Acceso</strong>). Asimismo, es su derecho solicitar la corrección de su información personal si está desactualizada (<strong>Rectificación</strong>); solicitar que la eliminemos de nuestros registros (<strong>Cancelación</strong>); y oponerse al uso de sus datos para fines específicos (<strong>Oposición</strong>).
            </p>
            <p>
              <em>Nota: El derecho de Cancelación de datos clínicos está condicionado al cumplimiento del plazo legal de retención de 5 años estipulado por la NOM-004-SSA3-2012.</em>
            </p>

            <h2 style={{ fontSize: '1.4rem', marginTop: '2.5rem', marginBottom: '1rem' }}>5. Portabilidad y Decreto de Digitalización 2026</h2>
            <p>
              Usted es dueño de su información médica. En cualquier momento puede solicitar a su médico la exportación de su expediente en formatos interoperables (HL7 / JSON), de acuerdo a los lineamientos del Decreto de Digitalización del Sector Salud en México.
            </p>

          </div>
        </article>
      </main>
    </div>
  );
}
