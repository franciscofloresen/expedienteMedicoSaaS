import { useQuery } from '@tanstack/react-query';
import { HardDrive } from 'lucide-react';
import { filesApi } from '../services/api';

const GIB = 1024 * 1024 * 1024;

function formatGiB(bytes: number): string {
  return `${(bytes / GIB).toFixed(bytes < GIB ? 2 : 1)} GB`;
}

export default function StorageUsageCard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['storage-usage'],
    queryFn: filesApi.usage,
    staleTime: 30_000,
  });

  if (isLoading) {
    return <div className="glass-card"><div className="spinner" /></div>;
  }
  if (isError || !data) {
    return null;
  }

  const enabled = data.quota_bytes > 0;
  const percent = Math.min(100, data.percent_used);
  const color = percent >= 90 ? 'var(--color-danger)' : percent >= 75 ? 'var(--color-warning)' : 'var(--color-primary)';

  return (
    <div className="glass-card animate-fade-in" style={{ animationDelay: '0.15s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: enabled ? '1.25rem' : 0 }}>
        <div style={{ backgroundColor: 'var(--color-primary-tint)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'var(--color-primary)' }}>
          <HardDrive size={24} />
        </div>
        <div style={{ minWidth: 0 }}>
          <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Archivos clínicos</h2>
          <p className="text-muted" style={{ margin: '0.2rem 0 0', fontSize: '0.88rem' }}>
            {enabled ? `${formatGiB(data.used_bytes)} usados de ${formatGiB(data.quota_bytes)}` : 'Disponible con el plan Pro'}
          </p>
        </div>
      </div>
      {enabled && (
        <>
          <div aria-label={`${percent}% del almacenamiento utilizado`} style={{ height: 10, background: 'var(--color-bg)', borderRadius: 5, overflow: 'hidden', border: '1px solid var(--color-border)' }}>
            <div style={{ width: `${percent}%`, height: '100%', background: color, transition: 'width 200ms ease' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '0.65rem', fontSize: '0.82rem' }}>
            <span style={{ color }}>{percent.toFixed(1)}% utilizado</span>
            <span className="text-muted">{formatGiB(data.available_bytes)} disponibles</span>
          </div>
          {data.reserved_bytes > 0 && (
            <p className="text-muted" style={{ margin: '0.65rem 0 0', fontSize: '0.78rem' }}>
              {formatGiB(data.reserved_bytes)} reservados por cargas en proceso.
            </p>
          )}
        </>
      )}
    </div>
  );
}
