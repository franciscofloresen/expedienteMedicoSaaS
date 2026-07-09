import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react';
import { publicApi } from '../services/api';

export default function VerifyDocument() {
  const { token } = useParams<{ token: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ['verify', token],
    queryFn: () => publicApi.verify(token!),
    enabled: !!token,
    retry: false,
  });

  const valid = data?.valid === true;

  return (
    <main style={{ minHeight: '100vh', background: 'var(--bg-app)', color: 'var(--text-main)', padding: '4rem 5%' }}>
      <div style={{ maxWidth: '720px', margin: '0 auto' }}>
        <Link to="/" style={{ color: 'var(--primary)', textDecoration: 'none' }}>CloudMedRecord</Link>
        <div className="glass-card" style={{ marginTop: '1.5rem', padding: '2rem' }}>
          {isLoading ? (
            <p>Verificando documento…</p>
          ) : error ? (
            <p>No se pudo verificar el documento.</p>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                {valid ? <CheckCircle2 color="var(--color-success)" /> : <AlertTriangle color="var(--color-danger)" />}
                <span className={valid ? 'badge badge-success' : 'badge badge-draft'}>
                  {valid ? 'Documento válido' : data?.status === 'revoked' ? 'Documento revocado' : 'No encontrado'}
                </span>
              </div>
              <h1 className="font-serif" style={{ marginTop: 0 }}>Verificación pública</h1>
              <dl style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '0.75rem', fontSize: '0.95rem' }}>
                <dt>Tipo</dt><dd>{data?.resource_type || 'N/A'}</dd>
                <dt>Folio</dt><dd className="mono">{data?.folio || 'N/A'}</dd>
                <dt>Médico</dt><dd>{data?.medico_nombre || 'N/A'}</dd>
                <dt>Cédula</dt><dd>{data?.medico_cedula || 'N/A'}</dd>
                <dt>Emisión</dt><dd>{data?.fecha_emision ? new Date(data.fecha_emision).toLocaleString() : 'N/A'}</dd>
                <dt>Hash</dt><dd className="mono" style={{ overflowWrap: 'anywhere' }}>{data?.hash || 'N/A'}</dd>
              </dl>
              <p style={{ marginTop: '1.5rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                <ShieldCheck size={16} /> {data?.privacy_notice || 'No se muestran datos clínicos sensibles en esta página.'}
              </p>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
