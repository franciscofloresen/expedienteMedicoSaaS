import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { User, Shield, Key, CreditCard, CheckCircle2, Edit2, Check, X, Download } from 'lucide-react';
import { UserProfile, useReverification } from '@clerk/react';
import { useToast } from '../hooks/useToast';
import UpgradeBanner from '../components/UpgradeBanner';
import StorageUsageCard from '../components/StorageUsageCard';
import ThemePicker from '../components/ThemePicker';
import { authApi, exportacionApi, expedientesApi } from '../services/api';

/** Save an already-fetched JSON document as a file download. */
function downloadJson(document_: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(document_, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** «Mis datos» — portabilidad: exportación completa por paciente y del índice. */
function MisDatosCard() {
  const { showToast } = useToast();
  const [selectedExpediente, setSelectedExpediente] = useState('');
  const [downloading, setDownloading] = useState<'indice' | 'expediente' | null>(null);

  // Both export endpoints demand step-up reauthentication; useReverification
  // opens the MFA modal transparently and retries (same pattern as signing).
  const fetchIndiceWithReauth = useReverification(exportacionApi.indiceConsultorio);
  const fetchExpedienteWithReauth = useReverification(exportacionApi.expediente);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: expedientes } = useQuery<any[]>({
    queryKey: ['expedientes'],
    queryFn: expedientesApi.getAll,
  });

  const handleDownloadIndice = async () => {
    setDownloading('indice');
    try {
      const first = await fetchIndiceWithReauth(undefined);
      const pacientes = [...first.pacientes];
      let cursor = first.next_cursor;
      while (cursor) {
        const page = await fetchIndiceWithReauth(cursor);
        pacientes.push(...page.pacientes);
        cursor = page.next_cursor;
      }
      downloadJson({ ...first, pacientes, next_cursor: null }, 'cloudmedrecord-indice-consultorio.json');
      showToast('Índice del consultorio descargado', 'success');
    } catch {
      showToast('No pudimos generar el índice. Intenta de nuevo.', 'error');
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadExpediente = async () => {
    if (!selectedExpediente) return;
    setDownloading('expediente');
    try {
      const doc = await fetchExpedienteWithReauth(selectedExpediente);
      const folio = doc?.expediente?.folio || selectedExpediente;
      downloadJson(doc, `cloudmedrecord-expediente-${folio}.json`);
      showToast('Expediente exportado. Los enlaces de archivos caducan en 15 minutos.', 'success');
    } catch {
      showToast('No pudimos exportar el expediente. Intenta de nuevo.', 'error');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="glass-card animate-fade-in" style={{ animationDelay: '0.15s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <div style={{ backgroundColor: 'var(--primary-light)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'var(--primary)' }}>
          <Download size={24} />
        </div>
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Mis datos</h2>
      </div>
      <p className="text-muted" style={{ marginTop: 0, marginBottom: '1.25rem', fontSize: '0.9rem' }}>
        Tus datos son tuyos. Descarga cuando quieras el expediente completo de cualquier paciente:
        incluye tus notas firmadas, recetas, consentimientos y los enlaces de descarga de tus
        archivos originales. Los enlaces caducan en 15 minutos; vuelve a generarlos cuando los
        necesites.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            className="form-input"
            style={{ flex: '1 1 220px', minWidth: 0 }}
            value={selectedExpediente}
            onChange={e => setSelectedExpediente(e.target.value)}
            aria-label="Paciente a exportar"
          >
            <option value="">Selecciona un paciente…</option>
            {(expedientes || []).map(exp => (
              <option key={exp.id} value={exp.id}>
                {exp.paciente_nombre} — {exp.folio}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-primary"
            style={{ whiteSpace: 'nowrap' }}
            disabled={!selectedExpediente || downloading !== null}
            onClick={handleDownloadExpediente}
          >
            <Download size={16} />
            {downloading === 'expediente' ? 'Generando…' : 'Descargar todo el expediente'}
          </button>
        </div>
        <div>
          <button
            type="button"
            className="btn btn-outline"
            disabled={downloading !== null}
            onClick={handleDownloadIndice}
          >
            <Download size={16} />
            {downloading === 'indice' ? 'Generando…' : 'Descargar índice del consultorio'}
          </button>
          <p className="text-muted" style={{ fontSize: '0.78rem', marginTop: '0.35rem', marginBottom: 0 }}>
            El índice lista tus pacientes y cuántos documentos tiene cada expediente, sin contenido
            clínico. Cada exportación queda registrada en la bitácora.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const updateProfileWithReauthentication = useReverification(authApi.updateProfile);

  const [isEditingProf, setIsEditingProf] = useState(false);
  const [editCedula, setEditCedula] = useState('');
  const [editEspecialidad, setEditEspecialidad] = useState('');
  const [editNotifEmail, setEditNotifEmail] = useState('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: profile, isLoading, isError } = useQuery<any>({
    queryKey: ['profile'],
    queryFn: authApi.getProfile,
    retry: 1
  });

  const updateMutation = useMutation({
    mutationFn: (data: { cedula: string; especialidad: string; notification_email: string }) =>
      updateProfileWithReauthentication(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      showToast('Datos actualizados correctamente', 'success');
      setIsEditingProf(false);
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || err?.data?.detail;
      showToast(typeof detail === 'string' ? detail : 'No pudimos actualizar tus datos profesionales.', 'error');
    }
  });

  const handleEdit = () => {
    setEditCedula(profile.cedula || '');
    setEditEspecialidad(profile.especialidad || '');
    setEditNotifEmail(profile.notification_email || '');
    setIsEditingProf(true);
  };

  const handleSave = () => {
    updateMutation.mutate({
      cedula: editCedula,
      especialidad: editEspecialidad,
      notification_email: editNotifEmail.trim()
    });
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <header style={{ marginBottom: '2rem' }}>
        <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>Configuración de la Clínica</h1>
        <p className="text-muted" style={{ marginTop: '0.5rem' }}>Gestiona tu perfil profesional y la seguridad de tus datos.</p>
      </header>
      
      <UpgradeBanner />

      {isLoading ? (
        <div className="loading-state">
          <div className="spinner" />
          <span>Cargando perfil profesional…</span>
        </div>
      ) : isError ? (
        <div className="empty-state glass-card">
          <div className="empty-state-title" style={{ color: 'var(--color-danger)' }}>No pudimos cargar la configuración</div>
          <p className="empty-state-hint">Revisa tu conexión o vuelve a iniciar sesión.</p>
        </div>
      ) : profile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Tarjeta de Perfil Profesional (Datos Médicos) */}
          <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ backgroundColor: 'var(--primary-light)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'var(--primary)' }}>
                  <User size={24} />
                </div>
                <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Datos Profesionales (NOM-004)</h2>
              </div>
              {!isEditingProf ? (
                  <button type="button" className="btn btn-outline" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} onClick={handleEdit}>
                  <Edit2 size={16} /> Editar
                </button>
              ) : (
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button type="button" className="btn btn-outline" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem', color: 'var(--error)' }} onClick={() => setIsEditingProf(false)}>
                    <X size={16} /> Cancelar
                  </button>
                  <button type="button" className="btn btn-primary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} onClick={handleSave} disabled={updateMutation.isPending}>
                    <Check size={16} /> {updateMutation.isPending ? 'Guardando…' : 'Guardar'}
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Cédula Profesional</label>
                {isEditingProf ? (
                  <input type="text" className="form-input" value={editCedula} placeholder="Ej. 1234567" onChange={e => setEditCedula(e.target.value)} />
                ) : (
                  <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{profile.cedula}</div>
                )}
              </div>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Especialidad</label>
                {isEditingProf ? (
                  <input type="text" className="form-input" value={editEspecialidad} placeholder="Ej. Medicina General" onChange={e => setEditEspecialidad(e.target.value)} />
                ) : (
                  <div>{profile.especialidad || 'No especificada'}</div>
                )}
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Correo de notificaciones</label>
                {isEditingProf ? (
                  <>
                    <input type="email" className="form-input" value={editNotifEmail} placeholder={profile.email} onChange={e => setEditNotifEmail(e.target.value)} />
                    <p className="text-muted" style={{ fontSize: '0.78rem', marginTop: '0.35rem' }}>
                      A dónde enviamos las confirmaciones de citas. Déjalo vacío para usar tu correo de acceso ({profile.email}).
                    </p>
                  </>
                ) : (
                  <div>{profile.notification_email || <span className="text-muted">Usando tu correo de acceso ({profile.email})</span>}</div>
                )}
              </div>
            </div>
          </div>

          {/* Portabilidad de datos (Entregable 1 — plan de pre-venta) */}
          <MisDatosCard />

          <StorageUsageCard />

            {/* Perfil de Usuario de Clerk */}
            <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s', padding: 0, overflow: 'hidden' }}>
              {/* Colors inherit from ClerkProvider's themed appearance (Fase 13A);
                  only layout is overridden here. */}
              <UserProfile
                appearance={{
                  elements: {
                    rootBox: {
                      width: '100%',
                    },
                    cardBox: {
                      width: '100%',
                      boxShadow: 'none',
                      margin: 0,
                    },
                    card: {
                      boxShadow: 'none',
                      border: 'none',
                      background: 'transparent',
                      width: '100%',
                      maxWidth: '100%',
                      margin: 0,
                    },
                    navbar: {
                      display: 'none'
                    },
                    scrollBox: {
                      borderRadius: '0',
                    },
                    pageScrollBox: {
                      padding: '1.5rem',
                    },
                    profileSection: {
                      padding: '0',
                      gap: '1rem',
                    }
                  }
                }}
              />
            </div>

          {/* Apariencia (Fase 13A) */}
          <ThemePicker />

          {/* Tarjeta de Seguridad y Facturación */}
          <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <div style={{ backgroundColor: 'var(--success)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'white' }}>
                <Shield size={24} />
              </div>
              <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Seguridad y Cumplimiento (NOM-004)</h2>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
                <Key size={24} color="var(--primary)" style={{ flexShrink: 0, marginTop: '0.25rem' }} />
                <div>
                  <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Cifrado de Base de Datos
                    <span className="badge badge-success" style={{ display: 'inline-flex', gap: '0.25rem', alignItems: 'center' }}>
                      <CheckCircle2 size={12} /> Activo
                    </span>
                  </h3>
                  <p className="text-muted" style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem' }}>
                    Los antecedentes y notas médicas se protegen con cifrado de base de datos para ayudar a documentar seguridad y cumplimiento operativo.
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem', backgroundColor: 'var(--bg-main)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
                <CreditCard size={24} color="var(--text-main)" style={{ flexShrink: 0, marginTop: '0.25rem' }} />
                <div>
                  <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem 0' }}>Suscripción Actual</h3>
                  <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
                    Plan <strong style={{ textTransform: 'capitalize' }}>{profile.plan}</strong>. Las opciones de facturación no están disponibles en este demo.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>
      ) : null}
    </div>
  );
}
