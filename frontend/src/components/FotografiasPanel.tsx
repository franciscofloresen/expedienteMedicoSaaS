/**
 * FotografiasPanel — clinical-photo metadata grouped for before/after comparison
 * (Fase 13). Self-contained. The image bytes are uploaded through the Archivos
 * (clinical-file) flow with category "fotografía clínica"; this panel manages the
 * clinical metadata sidecar (category, laterality, zone, date, comparison group)
 * and pairs photos for comparison. No biometrics.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Images, Trash2, Info } from 'lucide-react';
import { fotografiasApi } from '../services/api';
import { groupPhotosForComparison } from '../utils/fotografias';
import { useToast } from '../hooks/useToast';
import type { FotografiaClinica } from '../types';

const CATEGORIA_LABEL: Record<string, string> = {
  antes: 'Antes',
  despues: 'Después',
  seguimiento: 'Seguimiento',
  general: 'General',
};

function metaLine(f: FotografiaClinica): string {
  return [
    f.zona_anatomica,
    f.lateralidad && f.lateralidad !== 'na' ? `lado ${f.lateralidad}` : null,
    f.fecha_toma ? new Date(f.fecha_toma).toLocaleDateString() : null,
  ]
    .filter(Boolean)
    .join(' · ');
}

export default function FotografiasPanel({ pacienteId }: { pacienteId: string }) {
  const qc = useQueryClient();
  const { showToast } = useToast();
  const { data: fotos = [] } = useQuery({
    queryKey: ['fotografias', pacienteId],
    queryFn: () => fotografiasApi.list(pacienteId),
  });
  const removeFoto = useMutation({
    mutationFn: (id: string) => fotografiasApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fotografias', pacienteId] }),
    onError: () => showToast('No se pudo eliminar la fotografía.', 'error'),
  });

  const groups = groupPhotosForComparison(fotos);

  return (
    <div className="glass-card" style={{ marginTop: '1.25rem' }} data-testid="fotografias-panel">
      <span className="overline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
        <Images size={15} /> Fotografías clínicas
      </span>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--color-muted)', marginBottom: '1rem' }}>
        <Info size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          Sube la imagen en <strong>Archivos</strong> con categoría "fotografía clínica" y su
          consentimiento específico; aquí se registran categoría, lateralidad, zona y grupo de
          comparación (antes/después). Sin biometría ni reconocimiento automático.
        </span>
      </div>

      {fotos.length === 0 ? (
        <span className="text-muted">Sin fotografías registradas.</span>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {groups.map((g) => (
            <div key={g.grupo ?? '__none__'} style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '0.75rem 0.9rem' }}>
              <div className="overline" style={{ fontSize: '0.68rem', marginBottom: '0.5rem' }}>
                {g.grupo ? `Comparación · ${g.grupo}` : 'Sin grupo de comparación'}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '0.75rem' }}>
                {g.fotos.map((f) => (
                  <div key={f.id} style={{ border: '1px solid var(--color-border)', borderRadius: '6px', padding: '0.6rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                      <span className="badge badge-draft">{CATEGORIA_LABEL[f.categoria] ?? f.categoria}</span>
                      <button type="button" className="btn-icon" aria-label="Eliminar fotografía" onClick={() => removeFoto.mutate(f.id)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-muted)' }}>{metaLine(f) || 'Sin metadatos adicionales'}</div>
                    {!f.consentimiento_id && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--color-danger)', marginTop: '0.3rem' }}>Falta consentimiento</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
