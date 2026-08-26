import { Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import {
  CalendarCheck,
  FileCheck2,
  Files,
  QrCode,
  Scale,
  ShieldCheck,
  Stethoscope,
} from 'lucide-react';
import { Show, SignInButton, SignUpButton, UserButton } from '@clerk/react';

/* La página de marketing es deliberadamente oscura siempre (vídeo con overlay,
   titular blanco): no debe heredar el tema claro de un médico con sesión
   iniciada. Toda su paleta y sus materiales viven scoped en `.landing-root`. */

const WHATSAPP_URL = 'https://wa.me/523121940941';
const DEMO_URL = `${WHATSAPP_URL}?text=${encodeURIComponent(
  'Hola, quiero agendar una demo de 15 minutos de CloudMedRecord',
)}`;

interface InfoCard {
  icon: LucideIcon;
  title: string;
  text: string;
  accent?: boolean;
}

const PILLARS: InfoCard[] = [
  {
    icon: ShieldCheck,
    title: 'Evidencia legal visible',
    text: 'Firma digital, hash SHA-256, bitácora y QR para verificar documentos sin mostrar datos clínicos sensibles.',
  },
  {
    icon: FileCheck2,
    title: 'Estética y dermatología',
    text: 'Consentimientos listos para procedimientos privados, recetas firmadas y expedientes ordenados para consulta diaria.',
  },
  {
    icon: CalendarCheck,
    title: 'Beta Fundador',
    text: '$499 MXN/mes para los primeros médicos. Incluye setup asistido, soporte directo y precio congelado 12 meses.',
  },
];

const INFO_CARDS: InfoCard[] = [
  {
    icon: Stethoscope,
    title: 'Para quién es',
    text: 'Médicos de medicina estética, dermatología y consultas privadas que documentan procedimientos y seguimiento.',
  },
  {
    icon: Files,
    title: 'Problemas que resuelve',
    text: 'Expedientes dispersos, recetas sin evidencia, consentimientos improvisados y dificultad para demostrar integridad documental.',
  },
  {
    icon: Scale,
    title: 'Aviso responsable',
    text: 'Ayuda a documentar mejor y considera NOM-004, NOM-024 y LFPDPPP; no promete cumplimiento garantizado ni sustituye asesoría legal.',
  },
  {
    icon: QrCode,
    title: 'Demo de 15 minutos',
    text: 'Expediente, nota firmada, documento imprimible, QR, consentimiento, receta y WhatsApp manual.',
    accent: true,
  },
];

function LandingNav() {
  return (
    <nav className="landing-nav" aria-label="Principal">
      <div className="landing-brand">
        <img src="/faviconC.png" alt="" />
        <div className="landing-brand-text">
          <span className="font-serif landing-brand-name">CloudMedRecord</span>
          <span className="tracking-widest landing-brand-tag">Clinical System</span>
        </div>
      </div>
      <div className="landing-nav-actions">
        <Show when="signed-out">
          <SignInButton mode="modal">
            <button className="landing-link-btn">Iniciar Sesión</button>
          </SignInButton>
          <SignUpButton mode="modal">
            <button className="landing-cta">Crear Cuenta</button>
          </SignUpButton>
        </Show>
        <Show when="signed-in">
          <Link to="/app" className="landing-dash-link">Ir al Dashboard</Link>
          <UserButton />
        </Show>
      </div>
    </nav>
  );
}

function LandingHero() {
  return (
    <section className="landing-hero" aria-label="Presentación">
      {/* El scrim garantiza contraste del titular sobre cualquier frame del
          vídeo; con reduced-motion el vídeo se oculta por CSS y queda solo
          el fondo (§14: nada de fondos en movimiento a pantalla completa). */}
      <video className="landing-hero-media" autoPlay muted loop playsInline>
        <source src="/videoMain.mp4" type="video/mp4" />
      </video>
      <div className="landing-hero-scrim" aria-hidden="true" />

      <div className="landing-hero-panel">
        <p className="landing-eyebrow">Beta Fundador para médicos privados</p>

        <h1 className="font-serif landing-display">
          Expediente clínico legal-first <br />
          <em className="landing-display-accent">para médicos en México.</em>
        </h1>

        <p className="landing-lede">
          Crea notas, recetas y consentimientos con firma digital, hash, bitácora
          y QR verificable. Diseñado para consultas privadas que quieren
          documentar mejor y protegerse ante reclamaciones.
        </p>

        <div className="landing-hero-actions">
          <SignUpButton mode="modal">
            <button className="landing-underline-link">Quiero probar la beta</button>
          </SignUpButton>
          <a className="landing-underline-link is-primary" href={DEMO_URL}>
            Agendar demo
          </a>
        </div>
      </div>
    </section>
  );
}

function LandingPillars() {
  return (
    <section className="landing-pillars" aria-labelledby="landing-pillars-title">
      <h2 id="landing-pillars-title" className="sr-only">Qué ofrece CloudMedRecord</h2>
      <div className="landing-section-inner landing-pillar-grid">
        {PILLARS.map(({ icon: Icon, title, text }) => (
          <article key={title} className="landing-pillar">
            <Icon size={36} className="landing-pillar-icon" aria-hidden="true" />
            <h3 className="font-serif landing-card-title">{title}</h3>
            <p className="landing-card-text">{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LandingInfo() {
  return (
    <section className="landing-info" aria-labelledby="landing-info-title">
      <h2 id="landing-info-title" className="sr-only">Para quién es y cómo ayuda</h2>
      <div className="landing-section-inner landing-info-grid">
        {INFO_CARDS.map(({ icon: Icon, title, text, accent }) => (
          <article
            key={title}
            className={`landing-info-card${accent ? ' is-accent' : ''}`}
          >
            <Icon size={24} className="landing-info-icon" aria-hidden="true" />
            <h3 className="landing-info-title">{title}</h3>
            <p className="landing-info-text">{text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="landing-footer">
      <span className="font-serif landing-footer-brand">CloudMedRecord</span>
      <nav className="landing-footer-links" aria-label="Legal y soporte">
        <Link to="/privacidad">Aviso de Privacidad</Link>
        <Link to="/seguridad-y-cumplimiento">Seguridad</Link>
        <a href={WHATSAPP_URL}>Soporte</a>
      </nav>
      <p className="landing-footer-note">
        &copy; {new Date().getFullYear()} CloudMedRecord. Clínicas modernas,
        protegidas legalmente.
      </p>
    </footer>
  );
}

export default function Landing() {
  return (
    <div className="landing-root">
      <LandingNav />
      <main>
        <LandingHero />
        <LandingPillars />
        <LandingInfo />
      </main>
      <LandingFooter />
    </div>
  );
}
