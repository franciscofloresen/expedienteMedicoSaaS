import { Link } from 'react-router-dom';
import { ShieldCheck, FileCheck2, KeyRound, Server, ScrollText } from 'lucide-react';

const blockStyle = {
  border: '1px solid var(--color-border)',
  borderRadius: '8px',
  padding: '1.25rem',
  background: 'var(--color-surface)',
};

export default function SeguridadCumplimiento() {
  return (
    <main style={{ minHeight: '100vh', background: 'var(--bg-app)', color: 'var(--text-main)' }}>
      <nav className="landing-nav" style={{ position: 'relative', background: 'var(--color-surface)' }}>
        <Link to="/" className="landing-brand" style={{ textDecoration: 'none' }}>
          <img src="/faviconC.png" alt="Logo" />
          <div className="landing-brand-text">
            <span className="font-serif landing-brand-name">CloudMedRecord</span>
            <span className="tracking-widest landing-brand-tag">Seguridad</span>
          </div>
        </Link>
        <Link to="/" className="landing-dash-link">Volver</Link>
      </nav>

      <section style={{ maxWidth: '1040px', margin: '0 auto', padding: '4rem 5%' }}>
        <div style={{ maxWidth: '760px', marginBottom: '2rem' }}>
          <span className="overline">Seguridad y cumplimiento</span>
          <h1 className="font-serif" style={{ fontSize: '2.6rem', lineHeight: 1.1, margin: '0.6rem 0 1rem' }}>
            Evidencia verificable para expedientes, recetas y consentimientos.
          </h1>
          <p style={{ color: 'var(--text-muted)', lineHeight: 1.7 }}>
            CloudMedRecord ayuda a médicos privados en México a documentar mejor y generar evidencia
            con firma digital, huella de integridad, bitácora y QR verificable. No promete certificación ni sustituye asesoría legal.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
          <section style={blockStyle}>
            <ShieldCheck color="var(--primary)" />
            <h2>Datos protegidos</h2>
            <p>Expedientes, pacientes, notas, recetas, citas y bitácora se aíslan por consultorio y se tratan como información clínica sensible.</p>
          </section>
          <section style={blockStyle}>
            <KeyRound color="var(--primary)" />
            <h2>Firma digital</h2>
            <p>La firma dentro del sistema vincula el contenido firmado con el médico, cédula, fecha y metadatos de integridad.</p>
          </section>
          <section style={blockStyle}>
            <FileCheck2 color="var(--primary)" />
            <h2>Huella de integridad</h2>
            <p>La huella del documento ayuda a detectar cambios en el contenido firmado y mostrar evidencia en documentos imprimibles.</p>
          </section>
          <section style={blockStyle}>
            <ScrollText color="var(--primary)" />
            <h2>Bitácora</h2>
            <p>Las acciones clínicas relevantes se registran con fecha, resultado y datos de contexto cuando aplica.</p>
          </section>
          <section style={blockStyle}>
            <Server color="var(--primary)" />
            <h2>Proveedores</h2>
            <p>La plataforma usa AWS para infraestructura, Clerk para autenticación y servicios de email para notificaciones.</p>
          </section>
          <section style={blockStyle}>
            <ShieldCheck color="var(--primary)" />
            <h2>Normas consideradas</h2>
            <p>El producto considera NOM-004, NOM-024 y LFPDPPP como guía de diseño documental y privacidad.</p>
          </section>
        </div>

        <div style={{ ...blockStyle, marginTop: '1rem', borderColor: 'rgba(212,168,67,0.45)' }}>
          <strong>Aviso responsable:</strong> CloudMedRecord ayuda a documentar y generar evidencia verificable;
          no sustituye asesoría legal ni garantiza por sí solo el cumplimiento total de obligaciones regulatorias.
        </div>
      </section>
    </main>
  );
}
