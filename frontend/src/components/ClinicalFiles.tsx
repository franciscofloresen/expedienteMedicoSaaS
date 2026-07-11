import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileText, LoaderCircle, ShieldCheck, Trash2, Upload } from 'lucide-react';
import { type ClinicalFile, filesApi } from '../services/api';
import { useToast } from '../hooks/useToast';

const MIB = 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < MIB) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / MIB).toFixed(1)} MB`;
}

function statusLabel(file: ClinicalFile): { text: string; className: string } {
  if (file.status === 'available') return { text: 'Seguro', className: 'badge badge-success' };
  if (file.status === 'quarantined') return { text: 'Bloqueado', className: 'badge badge-danger' };
  if (file.status === 'scan_failed') return { text: 'Revisión requerida', className: 'badge badge-danger' };
  return { text: 'Analizando', className: 'badge badge-draft' };
}

export default function ClinicalFiles({ expedienteId }: { expedienteId: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [category, setCategory] = useState<ClinicalFile['category']>('other');
  const client = useQueryClient();
  const { showToast } = useToast();
  const { data: files = [], isLoading } = useQuery({
    queryKey: ['clinical-files', expedienteId],
    queryFn: () => filesApi.list(expedienteId),
    refetchInterval: (query) => query.state.data?.some((file) => file.status === 'scanning') ? 5_000 : false,
  });
  const { data: usage } = useQuery({
    queryKey: ['storage-usage'],
    queryFn: filesApi.usage,
    staleTime: 30_000,
  });
  const storageEnabled = (usage?.quota_bytes ?? 0) > 0;
  const storageLoading = usage === undefined;

  const uploadMutation = useMutation({
    mutationFn: (file: File) => filesApi.upload(expedienteId, file, category),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['clinical-files', expedienteId] });
      client.invalidateQueries({ queryKey: ['storage-usage'] });
      if (inputRef.current) inputRef.current.value = '';
      showToast('Archivo cargado. El análisis de seguridad está en proceso.', 'success');
    },
    onError: (error: Error) => showToast(error.message || 'No pudimos cargar el archivo.', 'error'),
  });
  const archiveMutation = useMutation({
    mutationFn: filesApi.archive,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['clinical-files', expedienteId] });
      showToast('Archivo retirado de la vista. Se conserva conforme al expediente clínico.', 'success');
    },
    onError: (error: Error) => showToast(error.message || 'No pudimos retirar el archivo.', 'error'),
  });

  const download = async (file: ClinicalFile) => {
    try {
      const { url } = await filesApi.downloadUrl(file.id);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.rel = 'noopener noreferrer';
      anchor.click();
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'No pudimos descargar el archivo.', 'error');
      client.invalidateQueries({ queryKey: ['clinical-files', expedienteId] });
    }
  };

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ margin: 0 }}>Archivos clínicos</h2>
          <p className="text-muted" style={{ margin: '0.35rem 0 0' }}>Análisis, radiografías, imágenes DICOM y documentos del paciente.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <select className="form-input" aria-label="Tipo de archivo clínico" value={category} onChange={(event) => setCategory(event.target.value as ClinicalFile['category'])} style={{ width: 'auto' }}>
            <option value="other">Otro documento</option>
            <option value="analysis">Análisis</option>
            <option value="xray">Radiografía / imagen</option>
            <option value="prescription">Prescripción</option>
            <option value="consent">Consentimiento</option>
          </select>
          <input
            ref={inputRef}
            type="file"
            hidden
            accept=".pdf,.dcm,.jpg,.jpeg,.png,.webp,application/pdf,application/dicom,image/jpeg,image/png,image/webp"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) uploadMutation.mutate(file);
            }}
          />
          <button className="btn btn-primary" type="button" onClick={() => inputRef.current?.click()} disabled={uploadMutation.isPending || !storageEnabled}>
            {uploadMutation.isPending ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}
            {uploadMutation.isPending ? 'Cargando…' : storageLoading ? 'Verificando…' : storageEnabled ? 'Subir archivo' : 'Requiere Pro'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="loading-state"><div className="spinner" /></div>
      ) : files.length === 0 ? (
        <div className="empty-state glass-card">
          <FileText size={40} color="var(--color-muted)" />
          <div className="empty-state-title">Sin archivos clínicos</div>
          <p className="empty-state-hint">Los archivos cargados para este paciente aparecerán aquí.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {files.map((file) => {
            const badge = statusLabel(file);
            return (
              <div key={file.id} className="glass-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', minWidth: 0 }}>
                  <div className="stat-icon"><FileText size={19} /></div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.filename}</div>
                    <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: '0.2rem' }}>
                      {formatSize(file.size_bytes)} · {new Date(file.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                  <span className={badge.className}><ShieldCheck size={11} /> {badge.text}</span>
                  <button className="btn-icon" type="button" aria-label={`Descargar ${file.filename}`} title="Descargar" disabled={file.status !== 'available'} onClick={() => download(file)}>
                    <Download size={17} />
                  </button>
                  <button className="btn-icon" type="button" aria-label={`Retirar ${file.filename}`} title="Retirar del expediente visible" onClick={() => {
                    if (window.confirm('El archivo dejará de verse, pero seguirá conservado por el periodo legal y continuará contando en tu almacenamiento.')) archiveMutation.mutate(file.id);
                  }}>
                    <Trash2 size={17} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
