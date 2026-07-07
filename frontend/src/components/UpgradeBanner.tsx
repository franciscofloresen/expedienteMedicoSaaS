import { useUser } from '@clerk/react';
import { AlertCircle } from 'lucide-react';

export default function UpgradeBanner() {
  const { user } = useUser();
  
  // If no user or user is already pro, don't show the banner
  if (!user || user.publicMetadata?.plan === 'pro') {
    return null;
  }

  return (
    <div
      className="no-print"
      style={{
        background: 'var(--color-gold-tint)',
        border: '1px solid rgba(212, 168, 67, 0.35)',
        borderRadius: 'var(--radius-lg)',
        padding: '1rem 1.25rem',
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem'
      }}
    >
      <div style={{ color: 'var(--color-gold)' }}>
        <AlertCircle size={22} />
      </div>
      <div style={{ flex: 1 }}>
        <h4 style={{ margin: 0, color: 'var(--color-text)', fontSize: '0.95rem', fontWeight: 600 }}>
          Estás en el Plan Básico (Límite: 5 Expedientes)
        </h4>
        <p style={{ margin: 0, color: 'var(--color-muted)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
          Para desbloquear expedientes ilimitados, contacta a soporte: franciscofloresenr@gmail.com o WhatsApp +523121940941
          {/* ponytail: simplificado al máximo */}
        </p>
      </div>
      <button
        className="btn btn-gold"
        onClick={() => window.open('https://wa.me/523121940941', '_blank')}
        style={{ whiteSpace: 'nowrap', padding: '0.5rem 1rem', fontSize: '0.875rem' }}
      >
        WhatsApp
      </button>
    </div>
  );
}
