import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { User, Shield, Key, CreditCard, CheckCircle2, Edit2, Check, X } from 'lucide-react';
import { UserProfile } from '@clerk/react';
import { useToast } from '../hooks/useToast';
import UpgradeBanner from '../components/UpgradeBanner';
import { authApi } from '../services/api';

export default function Settings() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [isEditingProf, setIsEditingProf] = useState(false);
  const [editCedula, setEditCedula] = useState('');
  const [editEspecialidad, setEditEspecialidad] = useState('');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: profile, isLoading, isError } = useQuery<any>({
    queryKey: ['profile'],
    queryFn: authApi.getProfile,
    retry: 1
  });

  const updateMutation = useMutation({
    mutationFn: (data: { cedula: string; especialidad: string }) => authApi.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      showToast('Datos actualizados correctamente', 'success');
      setIsEditingProf(false);
    },
    onError: () => {
      showToast('Error al actualizar datos', 'error');
    }
  });

  const handleEdit = () => {
    setEditCedula(profile.cedula || '');
    setEditEspecialidad(profile.especialidad || '');
    setIsEditingProf(true);
  };

  const handleSave = () => {
    updateMutation.mutate({
      cedula: editCedula,
      especialidad: editEspecialidad
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
        <div style={{ textAlign: 'center', padding: '3rem' }}>Cargando perfil...</div>
      ) : isError ? (
        <div className="glass-card" style={{ textAlign: 'center', color: 'var(--error)' }}>
          No se pudo cargar la configuración. Verifica tu conexión.
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
                <button className="btn btn-outline" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} onClick={handleEdit}>
                  <Edit2 size={16} /> Editar
                </button>
              ) : (
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="btn btn-outline" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem', color: 'var(--error)' }} onClick={() => setIsEditingProf(false)}>
                    <X size={16} /> Cancelar
                  </button>
                  <button className="btn btn-primary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }} onClick={handleSave} disabled={updateMutation.isPending}>
                    <Check size={16} /> {updateMutation.isPending ? 'Guardando...' : 'Guardar'}
                  </button>
                </div>
              )}
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Cédula Profesional</label>
                {isEditingProf ? (
                  <input type="text" className="form-input" value={editCedula} onChange={e => setEditCedula(e.target.value)} />
                ) : (
                  <div style={{ fontFamily: 'monospace', fontWeight: 600 }}>{profile.cedula}</div>
                )}
              </div>
              <div>
                <label className="text-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Especialidad</label>
                {isEditingProf ? (
                  <input type="text" className="form-input" value={editEspecialidad} onChange={e => setEditEspecialidad(e.target.value)} />
                ) : (
                  <div>{profile.especialidad || 'No especificada'}</div>
                )}
              </div>
            </div>
          </div>

            {/* Perfil de Usuario de Clerk */}
            <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s', padding: 0, overflow: 'hidden' }}>
              <UserProfile 
                appearance={{
                  variables: {
                    colorPrimary: '#00C2B8',
                    colorPrimaryForeground: '#04211F',
                    fontFamily: "'Inter', sans-serif",
                    colorBackground: '#161B22',
                    colorForeground: '#E6EDF3',
                    colorMutedForeground: '#7D8590',
                    colorInput: '#0D1117',
                    colorInputForeground: '#E6EDF3',
                    colorNeutral: '#E6EDF3',
                    colorBorder: '#21262D',
                  },
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
                    Todos los antecedentes y notas médicas de tus pacientes están protegidos con cifrado de base de datos (TDE) asegurando el cumplimiento de la NOM-024.
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
