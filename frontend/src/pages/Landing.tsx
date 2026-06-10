import { Link } from 'react-router-dom';
import { Activity, ShieldCheck, Zap, FileText, ChevronRight } from 'lucide-react';

export default function Landing() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-app)' }}>
      {/* Public Navbar */}
      <nav style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between', 
        padding: '1.25rem 5%', 
        backgroundColor: 'var(--bg-card)',
        borderBottom: '1px solid var(--border-light)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        background: 'rgba(255, 255, 255, 0.85)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', padding: '0.5rem', borderRadius: '10px', color: 'white', display: 'flex' }}>
            <Activity size={24} />
          </div>
          <span style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-main)' }}>MedRecord</span>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/login" className="btn btn-outline" style={{ border: 'none', fontWeight: 600 }}>Iniciar Sesión</Link>
          <Link to="/register" className="btn btn-primary" style={{ borderRadius: '100px', padding: '0.5rem 1.25rem' }}>Empezar Gratis</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <main style={{ flex: 1 }}>
        <section style={{ 
          padding: '8rem 5% 6rem 5%', 
          textAlign: 'center', 
          maxWidth: '900px', 
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '2rem'
        }}>
          <div className="badge" style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary)' }}>Cumplimiento NOM-024 y LFPDPPP</div>
          <h1 style={{ fontSize: '4rem', fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1.1, margin: 0 }}>
            El expediente clínico del futuro, <span style={{ color: 'var(--primary)' }}>hoy.</span>
          </h1>
          <p style={{ fontSize: '1.25rem', color: 'var(--text-muted)', maxWidth: '600px', lineHeight: 1.6 }}>
            Gestiona tus pacientes de forma segura, inmutable y rápida. Un diseño ultralimpio pensado para que los médicos dediquen más tiempo a consultar y menos a escribir.
          </p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
            <Link to="/register" className="btn btn-primary" style={{ borderRadius: '100px', padding: '1rem 2rem', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Crear mi Clínica <ChevronRight size={20} />
            </Link>
            <Link to="/privacidad" className="btn btn-outline" style={{ borderRadius: '100px', padding: '1rem 2rem', fontSize: '1.1rem' }}>
              Conocer más
            </Link>
          </div>
        </section>

        {/* Features Section */}
        <section style={{ padding: '5rem 5%', backgroundColor: 'var(--bg-card)' }}>
          <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '3rem' }}>
            
            <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.03)' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: 'rgba(52, 199, 89, 0.1)', color: 'var(--success)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem auto' }}>
                <ShieldCheck size={32} />
              </div>
              <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Auditoría Inmutable</h3>
              <p style={{ color: 'var(--text-muted)' }}>Cada nota firmada se sella digitalmente. Cumplimos con los estándares más estrictos de privacidad en México.</p>
            </div>

            <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.03)' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: 'rgba(0, 122, 255, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem auto' }}>
                <Zap size={32} />
              </div>
              <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Diseño Quirúrgico</h3>
              <p style={{ color: 'var(--text-muted)' }}>Una interfaz sin distracciones, ultrarrápida y diseñada con el mismo cuidado que usas con tus pacientes.</p>
            </div>

            <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.03)' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', backgroundColor: 'rgba(88, 86, 214, 0.1)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem auto' }}>
                <FileText size={32} />
              </div>
              <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Digitalización 2026</h3>
              <p style={{ color: 'var(--text-muted)' }}>Preparado para el Decreto de Digitalización del Sector Salud. Tú eres dueño de tu información.</p>
            </div>

          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{ padding: '3rem 5%', borderTop: '1px solid var(--border-light)', backgroundColor: 'var(--bg-app)', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginBottom: '1.5rem' }}>
          <Link to="/privacidad" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Aviso de Privacidad</Link>
          <a href="#" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Términos de Servicio</a>
          <a href="#" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Contacto</a>
        </div>
        <p>&copy; {new Date().getFullYear()} MedRecord. Todos los derechos reservados.</p>
      </footer>
    </div>
  );
}
