import { Link } from 'react-router-dom';
import { ShieldCheck, Zap, FileText } from 'lucide-react';
import { Show, SignInButton, SignUpButton, UserButton } from '@clerk/react';

export default function Landing() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-app)', color: 'var(--text-main)' }}>
      
      {/* Navbar Transparente / Elegante */}
      <nav style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        padding: '1.5rem 5%', 
        position: 'fixed',
        top: 0,
        width: '100%',
        zIndex: 50,
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* ponytail: simple img tag for logo instead of icon component */}
          <img src="/faviconC.png" alt="Logo" style={{ height: '32px', width: 'auto' }} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="font-serif" style={{ fontSize: '1.4rem', fontWeight: 600, color: 'white', lineHeight: 1 }}>CloudMedRecord</span>
            <span className="tracking-widest" style={{ fontSize: '0.6rem', textTransform: 'uppercase', color: 'rgba(255,255,255,0.7)', marginTop: '0.1rem' }}>Clinical System</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.2em', fontWeight: 500, color: 'white' }}>
          <Show when="signed-out">
            <SignInButton mode="modal">
              <button style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer', fontSize: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit', fontWeight: 'inherit', transition: 'color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary-light)'} onMouseLeave={(e) => e.currentTarget.style.color = 'white'}>
                Iniciar Sesión
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button style={{ backgroundColor: 'var(--primary)', color: 'white', border: 'none', padding: '0.75rem 1.5rem', borderRadius: '4px', cursor: 'pointer', fontSize: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit', fontWeight: 'inherit', transition: 'background-color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--primary-dark)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--primary)'}>
                Crear Cuenta
              </button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <Link to="/app" style={{ color: 'white', borderBottom: '1px solid white', paddingBottom: '0.25rem', textDecoration: 'none', transition: 'all 0.2s', marginRight: '1rem' }} onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--primary-light)'; e.currentTarget.style.borderColor = 'var(--primary-light)'; }} onMouseLeave={(e) => { e.currentTarget.style.color = 'white'; e.currentTarget.style.borderColor = 'white'; }}>Ir al Dashboard</Link>
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
              backgroundColor: 'rgba(255, 255, 255, 0.85)', 
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              padding: '4rem 3rem',
              borderRadius: '24px',
              maxWidth: '900px',
              margin: '0 auto',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              border: '1px solid rgba(255, 255, 255, 0.5)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', marginBottom: '2rem' }}>
              <span style={{ height: '1px', width: '2rem', backgroundColor: 'var(--primary)' }}></span>
              <span className="tracking-widest" style={{ textTransform: 'uppercase', fontSize: '0.75rem', fontWeight: 700, color: 'var(--primary)' }}>Exclusivo para Profesionales</span>
              <span style={{ height: '1px', width: '2rem', backgroundColor: 'var(--primary)' }}></span>
            </div>

            <h1 className="font-serif" style={{ fontSize: 'clamp(2.5rem, 5vw, 5rem)', fontWeight: 600, lineHeight: 1.1, margin: '0 0 1.5rem 0', color: 'var(--text-main)' }}>
              El estándar dorado en <br />
              <span style={{ fontStyle: 'italic', color: 'var(--primary)' }}>expediente clínico.</span>
            </h1>

            <p style={{ fontSize: '1.1rem', fontWeight: 400, color: 'var(--text-muted)', maxWidth: '600px', margin: '0 auto 3rem auto', lineHeight: 1.8 }}>
              Un software diseñado con precisión quirúrgica. Gestión inmutable, rápida y adaptada a la normativa mexicana para proteger la práctica médica.
            </p>

            <div style={{ display: 'flex', gap: '2rem', justifyContent: 'center', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.15em', fontWeight: 700 }}>
              <SignUpButton mode="modal">
                <button style={{ background: 'transparent', border: 'none', borderBottom: '1px solid transparent', color: 'var(--text-main)', cursor: 'pointer', fontSize: 'inherit', letterSpacing: 'inherit', textTransform: 'inherit', fontWeight: 'inherit', padding: 0, paddingBottom: '0.25rem', transition: 'all 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.color = 'var(--primary)'} onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-main)'}>Crear Clínica</button>
              </SignUpButton>
              <Link to="/privacidad" style={{ color: 'var(--primary)', textDecoration: 'none', borderBottom: '1px solid transparent', paddingBottom: '0.25rem', transition: 'all 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.borderBottomColor = 'var(--primary)'} onMouseLeave={(e) => e.currentTarget.style.borderBottomColor = 'transparent'}>Cumplimiento Legal</Link>
            </div>
          </div>

        </div>


      </section>

      {/* Banner de Características "Luxury" */}
      <section style={{ backgroundColor: '#ffffff', color: 'var(--text-main)', padding: '5rem 0', position: 'relative', zIndex: 30 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 5%', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '3rem', textAlign: 'center' }}>
          
          <div 
            style={{ padding: '2rem 1rem' }}
          >
            <ShieldCheck size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Auditoría Inmutable</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>Cada nota firmada se sella digitalmente. Cumplimos estrictamente con la NOM-004 y NOM-024.</p>
          </div>

          <div 
            style={{ padding: '2rem 1rem', borderLeft: '1px solid var(--border-light)', borderRight: '1px solid var(--border-light)' }}
          >
            <Zap size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Rapidez Extrema</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>Interfaz minimalista diseñada para que dediques más tiempo al paciente y menos al teclado.</p>
          </div>

          <div 
            style={{ padding: '2rem 1rem' }}
          >
            <FileText size={36} color="var(--primary)" style={{ margin: '0 auto 1.5rem auto' }} />
            <h3 className="font-serif" style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 600 }}>Listo para 2026</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: 1.6, fontWeight: 300 }}>Infraestructura interoperable alineada con el próximo Decreto de Digitalización del Sector Salud.</p>
          </div>

        </div>
      </section>

      {/* Footer Minimalista */}
      <footer style={{ padding: '4rem 5%', backgroundColor: 'var(--bg-app)', borderTop: '1px solid var(--border-light)' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <span className="font-serif" style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '1.5rem' }}>CloudMedRecord</span>
          <div style={{ display: 'flex', gap: '2rem', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '3rem' }}>
            <Link to="/privacidad" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Aviso de Privacidad</Link>
            <a href="#" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Términos</a>
            <a href="https://wa.me/523121940941" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Soporte</a>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>&copy; {new Date().getFullYear()} CloudMedRecord. Clínicas modernas, protegidas legalmente.</p>
        </div>
      </footer>
    </div>
  );
}
