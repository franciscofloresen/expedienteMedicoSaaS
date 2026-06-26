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
        background: 'linear-gradient(90deg, rgba(255,149,0,0.1), rgba(255,59,48,0.1))', 
        border: '1px solid rgba(255,149,0,0.3)',
        borderRadius: '12px',
        padding: '1rem 1.5rem',
        marginBottom: '1.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        boxShadow: '0 4px 12px rgba(255,149,0,0.05)'
      }}
    >
      <div style={{ color: '#FF9500' }}>
        <AlertCircle size={24} />
      </div>
      <div style={{ flex: 1 }}>
        <h4 style={{ margin: 0, color: 'var(--text-main)', fontSize: '1rem', fontWeight: 600 }}>
          Estás en el Plan Básico (Límite: 5 Expedientes)
        </h4>
        <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
          Para desbloquear expedientes ilimitados, contacta a soporte: franciscofloresenr@gmail.com o WhatsApp +523121940941
          {/* ponytail: simplificado al máximo */}
        </p>
      </div>
      <button 
        className="btn btn-primary"
        onClick={() => window.open('https://wa.me/523121940941', '_blank')}
        style={{ whiteSpace: 'nowrap', padding: '0.5rem 1rem', fontSize: '0.875rem' }}
      >
        WhatsApp
      </button>
    </div>
  );
}
