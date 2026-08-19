import { Link } from 'react-router-dom';
import { CalendarCheck, FileCheck2, QrCode, ShieldCheck } from 'lucide-react';
import { Show, SignInButton, SignUpButton, UserButton } from '@clerk/react';

export default function Landing() {
  return (
    // The marketing page is intentionally always dark (photo overlays, white
    // headline text) — it must not inherit a signed-in doctor's light theme.
    <div className="landing-root" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      
      {/* Navbar Transparente / Elegante */}
      <nav className="landing-nav">
        <div className="landing-brand">
          {/* ponytail: simple img tag for logo instead of icon component */}
          <img src="/faviconC.png" alt="Logo" />
          <div className="landing-brand-text">
            <span className="font-serif landing-brand-name">CloudMedRecord</span>
            <span className="tracking-widest landing-brand-tag">Clinical System</span>
          </div>
        </div>
        <div className="landing-nav-actions">
          <Show when="signed-out">
            <SignInButton mode="modal">
              <button className="landing-link-btn" onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary-light)'} onMouseLeave={(e) => e.currentTarget.style.color = 'white'}>
                Iniciar Sesión
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="landing-cta" onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--primary-hover)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--primary)'}>
                Crear Cuenta
              </button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <Link to="/app" className="landing-dash-link" style={{ marginRight: '1rem' }} onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--primary-light)'; e.currentTarget.style.borderColor = 'var(--primary-light)'; }} onMouseLeave={(e) => { e.currentTarget.style.color = 'white'; e.currentTarget.style.borderColor = 'white'; }}>Ir al Dashboard</Link>
            <UserButton />
          </Show>
        </div>
      </nav>

      {/* Hero Section con Video */}
      <section style={{ position: 'relative', height: '100vh', minHeight: '600px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
        
        {/* Video Background */}
        <video 
          autoPlay 
          muted 
          loop 
          playsInline 
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'cover', zIndex: 0 }}
        >
          <source src="/videoMain.mp4" type="video/mp4" />
        </video>

        {/* Overlay Azul/Oscuro */}
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0, 15, 30, 0.6)', zIndex: 10 }}></div>
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', background: 'linear-gradient(to top, rgba(0,0,0,0.8), transparent)', zIndex: 10 }}></div>

        {/* Contenido Central */}
        <div style={{ position: 'relative', zIndex: 20, textAlign: 'center', padding: '0 5%' }}>
          
          <div
            style={{
              backgroundColor: 'rgba(13, 17, 23, 0.82)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              padding: '4rem 3rem',
              borderRadius: '24px',
              maxWidth: '900px',
              margin: '0 auto',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
              border: '1px solid rgba(230, 237, 243, 0.12)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', marginBottom: '2rem' }}>
              <span style={{ height: '1px', width: '2rem', backgroundColor: 'var(--primary)' }}></span>
              <span className="tracking-widest" style={{ textTransform: 'uppercase', fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)' }}>Beta Fundador para médicos privados</span>
              <span style={{ height: '1px', width: '2rem', backgroundColor: 'var(--primary)' }}></span>
            </div>

            <h1 className="font-serif" style={{ fontSize: 'clamp(2.5rem, 5vw, 5rem)', fontWeight: 600, lineHeight: 1.1, margin: '0 0 1.5rem 0', color: 'var(--text-main)' }}>
              Expediente clínico legal-first <br />
              <span style={{ fontStyle: 'italic', color: 'var(--primary)' }}>para médicos en México.</span>
            </h1>

            <p style={{ fontSize: '1.1rem', fontWeight: 400, color: 'var(--text-muted)', maxWidth: '600px', margin: '0 auto 3rem auto', lineHeight: 1.8 }}>
              Crea notas, recetas y consentimientos con firma digital, hash, bitácora y QR verificable. Diseñado para consultas privadas que quieren documentar mejor y protegerse ante reclamaciones.
            </p>

            <div style={{ display: 'flex', gap: '2rem', justifyContent: 'center', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.15em', fontWeight: 700 }}>
              <SignUpButton mode="modal">
                <button style={{ background: 'transparent', border: 'none', borderBottom: '1px solid transparent', color: 'var(--text-main)', cursor: 'pointer', fontSize: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit', fontWeight: 'inherit', padding: 0, paddingBottom: '0.25rem', transition: 'all 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary)'} onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-main)'}>Quiero probar la beta</button>
              </SignUpButton>
              <a href="https://wa.me/523121940941?text=Hola%2C%20quiero%20agendar%20una%20demo%20de%2015%20minutos%20de%20CloudMedRecord" style={{ color: 'var(--primary)', textDecoration: 'none', borderBottom: '1px solid transparent', paddingBottom: '0.25rem', transition: 'all 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.borderBottomColor = 'var(--primary)'} onMouseLeave={(e) => e.currentTarget.style.borderBottomColor = 'transparent'}>Agendar demo</a>
            </div>
          </div>

        </div>


      </section>

      {/* Banner de Características */}
      <section style={{ backgroundColor: 'var(--color-surface)', color: 'var(--text-main)', borderTop: '1px solid var(--color-border)', padding: '5rem 0', position: 'relative', zIndex: 30 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 5%', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '3rem', textAlign: 'center' }}>
          
          <div 
            style={{ padding: '2rem 1rem' }}
          >
            <ShieldCheck size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Evidencia legal visible</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>Firma digital, hash SHA-256, bitácora y QR para verificar documentos sin mostrar datos clínicos sensibles.</p>
          </div>

          <div 
            style={{ padding: '2rem 1rem', borderLeft: '1px solid var(--border-light)', borderRight: '1px solid var(--border-light)' }}
          >
            <FileCheck2 size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Estética y dermatología</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>Consentimientos listos para procedimientos privados, recetas firmadas y expedientes ordenados para consulta diaria.</p>
          </div>

          <div 
            style={{ padding: '2rem 1rem' }}
          >
            <CalendarCheck size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Beta Fundador</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>$499 MXN/mes para los primeros médicos. Incluye setup asistido, soporte directo y precio congelado 12 meses.</p>
          </div>

        </div>
      </section>

      <section style={{ padding: '4rem 5%', background: 'var(--bg-app)' }}>
        <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
          {[
            ['Para quién es', 'Médicos de medicina estética, dermatología y consultas privadas que documentan procedimientos y seguimiento.'],
            ['Problemas que resuelve', 'Expedientes dispersos, recetas sin evidencia, consentimientos improvisados y dificultad para demostrar integridad documental.'],
            ['Aviso responsable', 'Ayuda a documentar mejor y considera NOM-004, NOM-024 y LFPDPPP; no promete cumplimiento garantizado ni sustituye asesoría legal.'],
          ].map(([title, text]) => (
            <div key={title} style={{ border: '1px solid var(--color-border)', borderRadius: 8, padding: '1.25rem', background: 'var(--color-surface)' }}>
              <h3 style={{ marginTop: 0 }}>{title}</h3>
              <p style={{ color: 'var(--text-muted)', lineHeight: 1.6 }}>{text}</p>
            </div>
          ))}
          <div style={{ border: '1px solid rgba(0,194,184,0.35)', borderRadius: 8, padding: '1.25rem', background: 'var(--color-surface)' }}>
            <QrCode color="var(--primary)" />
            <h3>Demo de 15 minutos</h3>
            <p style={{ color: 'var(--text-muted)' }}>Expediente, nota firmada, documento imprimible, QR, consentimiento, receta y WhatsApp manual.</p>
          </div>
        </div>
      </section>

      {/* Footer Minimalista */}
      <footer style={{ padding: '4rem 5%', backgroundColor: 'var(--bg-app)', borderTop: '1px solid var(--border-light)' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <span className="font-serif" style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '1.5rem' }}>CloudMedRecord</span>
          <div style={{ display: 'flex', gap: '2rem', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '3rem' }}>
            <Link to="/privacidad" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Aviso de Privacidad</Link>
            <Link to="/seguridad-y-cumplimiento" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Seguridad</Link>
            <a href="https://wa.me/523121940941" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Soporte</a>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>&copy; {new Date().getFullYear()} CloudMedRecord. Clínicas modernas, protegidas legalmente.</p>
        </div>
      </footer>
    </div>
  );
}
