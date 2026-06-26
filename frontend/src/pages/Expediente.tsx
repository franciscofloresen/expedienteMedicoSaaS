/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, type FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, X, FileSignature, Edit3, Lock, ShieldCheck, Calendar, Printer, Activity, RefreshCcw } from 'lucide-react';
import { expedientesApi, notasApi, pacientesApi } from '../services/api';
import type { Nota, NotaCreate } from '../types';
import { useToast } from '../hooks/useToast';
import { useAutosave } from '../hooks/useAutosave';
import { useEffect } from 'react';
import Modal from '../components/Modal';


export default function Expediente() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { showToast } = useToast();
  
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);
  const [editingNota, setEditingNota] = useState<Nota | null>(null);
  
  const [isSignModalOpen, setIsSignModalOpen] = useState(false);
  const [notaToSign, setNotaToSign] = useState<Nota | null>(null);

  const [isAntecedentesModalOpen, setIsAntecedentesModalOpen] = useState(false);

  // Autosave Draft
  const { draft, hasDraft, draftAge, saveDraft, clearDraft, lastSaveSecondsAgo } = useAutosave<any>(`nota-${id}`);

  // Consent state
  const [consentAccepted, setConsentAccepted] = useState(false);

  // Fetch Patient
  const { data: paciente } = useQuery({
    queryKey: ['paciente', id],
    queryFn: () => pacientesApi.getById(id!)
  });

  // Fetch Expediente 
  const { data: expediente, isLoading: isLoadingExpediente } = useQuery({
    queryKey: ['expediente', id],
    queryFn: () => expedientesApi.getByPacienteId(id as string)
  });

  // Fetch Notas
  const { data: notas = [], isLoading: isLoadingNotas } = useQuery({
    queryKey: ['notas', expediente?.id],
    queryFn: () => notasApi.getByExpedienteId(expediente?.id as string),
    enabled: !!expediente?.id
  });

  useEffect(() => {
    if (window.location.hash && notas.length > 0) {
      setTimeout(() => {
        document.getElementById(window.location.hash.substring(1))?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }, [notas]);

  // Create Expediente
  const createExpedienteMutation = useMutation({
    mutationFn: async () => {
      // Crear expediente (implica consentimiento)
      return expedientesApi.create({ paciente_id: id! });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['expediente', id] });
      client.invalidateQueries({ queryKey: ['auditLogs'] }); // Refrescar bitácora en dashboard
      showToast("Expediente creado y consentimiento registrado", "success");
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onError: (err: any) => {
      const message = err.response?.data?.detail || err.message || "Error al crear el expediente";
      showToast(message, "error");
    }
  });

  const updateAntecedentesMutation = useMutation({
    mutationFn: (antecedentes: string) => expedientesApi.updateAntecedentes(expediente!.id, antecedentes),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['expediente', id] });
      setIsAntecedentesModalOpen(false);
      showToast("Antecedentes actualizados exitosamente", "success");
    },
    onError: () => {
      showToast("Error al actualizar antecedentes", "error");
    }
  });

  const handleUpdateAntecedentes = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const text = formData.get('antecedentes') as string;
    updateAntecedentesMutation.mutate(text);
  };

  const formatContenido = (contenido: any) => {
    if (!contenido) return 'Sin evolución registrada.';
    if (typeof contenido === 'string') return contenido;
    
    // Check if it's our standard JSON structure
    if (contenido.motivo || contenido.subjetivo) {
      const parts = [];
      if (contenido.motivo) parts.push(`Motivo de consulta:\n${contenido.motivo}`);
      if (contenido.subjetivo) parts.push(`Subjetivo:\n${contenido.subjetivo}`);
      if (contenido.objetivo) parts.push(`Objetivo:\n${contenido.objetivo}`);
      if (contenido.analisis) parts.push(`Análisis:\n${contenido.analisis}`);
      if (contenido.plan) parts.push(`Plan:\n${contenido.plan}`);
      return parts.join('\n\n');
    }
    
    // Fallback formats
    if (contenido.evolucion_y_actualizacion_cuadro) return contenido.evolucion_y_actualizacion_cuadro;
    if (contenido.contenido) return contenido.contenido;

    // Last resort
    return Object.entries(contenido)
      .filter(([k]) => k !== 'diagnosticos')
      .map(([k, v]) => `${k.charAt(0).toUpperCase() + k.slice(1)}: ${v}`)
      .join('\n\n');
  };

  // Create Nota (Draft)
  const draftNotaMutation = useMutation({
    mutationFn: (payload: NotaCreate) => notasApi.create(payload),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSidePanelOpen(false);
      setEditingNota(null);
      clearDraft();
      showToast("Borrador creado", "success");
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Error al guardar el borrador";
      showToast(message, "error");
    }
  });

  const updateNotaMutation = useMutation({
    mutationFn: (payload: { id: string, data: Partial<NotaCreate> }) => notasApi.update(payload.id, payload.data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSidePanelOpen(false);
      setEditingNota(null);
      clearDraft();
      showToast("Borrador actualizado", "success");
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Error al actualizar el borrador";
      showToast(message, "error");
    }
  });

  const signNotaMutation = useMutation({
    mutationFn: (notaId: string) => notasApi.firmar(notaId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSignModalOpen(false);
      setNotaToSign(null);
      showToast("Nota firmada y bloqueada exitosamente", "success");
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Error al firmar la nota";
      showToast(message, "error");
      setIsSignModalOpen(false);
    }
  });



  const handleSubmitNota = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!expediente) return;

    const formData = new FormData(e.currentTarget);
    
    const contenido = {
      evolucion_y_actualizacion_cuadro: formData.get('evolucion') as string,
    };
    
    const signos_vitales = {
      frecuencia_cardiaca: Number(formData.get('fc')),
      frecuencia_respiratoria: Number(formData.get('fr')),
      temperatura: Number(formData.get('temp')),
      tension_arterial: formData.get('ta') as string
    };

    if (editingNota) {
      updateNotaMutation.mutate({
        id: editingNota.id,
        data: {
          contenido,
          signos_vitales,
          diagnosticos: [formData.get('diagnostico') as string],
          tratamiento: formData.get('tratamiento') as string
        }
      });
    } else {
      draftNotaMutation.mutate({
        expediente_id: expediente.id,
        tipo_nota: 'evolucion',
        contenido,
        signos_vitales,
        diagnosticos: [formData.get('diagnostico') as string],
        tratamiento: formData.get('tratamiento') as string
      });
    }
  };

  const handleFormChange = (e: FormEvent<HTMLFormElement>) => {
    if (editingNota) return; // Only autosave new drafts
    const formData = new FormData(e.currentTarget);
    saveDraft({
      fc: formData.get('fc'),
      fr: formData.get('fr'),
      temp: formData.get('temp'),
      ta: formData.get('ta'),
      evolucion: formData.get('evolucion'),
      diagnostico: formData.get('diagnostico'),
      tratamiento: formData.get('tratamiento')
    });
  };

  const applyDraft = () => {
    if (!draft) return;
    const form = document.getElementById('nota-form') as HTMLFormElement;
    if (!form) return;
    
    // Helper to set value
    const setVal = (name: string, val: any) => {
      if (val) {
        const input = form.elements.namedItem(name) as HTMLInputElement | HTMLTextAreaElement;
        if (input) input.value = val;
      }
    };

    setVal('fc', draft.fc);
    setVal('fr', draft.fr);
    setVal('temp', draft.temp);
    setVal('ta', draft.ta);
    setVal('evolucion', draft.evolucion);
    setVal('diagnostico', draft.diagnostico);
    setVal('tratamiento', draft.tratamiento);
    showToast("Borrador recuperado", "success");
  };

  const confirmSign = (nota: Nota) => {
    setNotaToSign(nota);
    setIsSignModalOpen(true);
  };

  if (isLoadingExpediente) return <div>Cargando expediente...</div>;

  if (!expediente) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
          <button className="btn btn-outline" style={{ padding: '0.5rem', borderRadius: '12px' }} onClick={() => navigate('/app')}>
            <ArrowLeft size={20} />
          </button>
          <h1 className="font-serif animate-fade-in" style={{ marginBottom: 0, fontSize: '2rem', fontWeight: 600, color: 'var(--text-main)' }}>Crear Expediente: {paciente?.nombre_completo}</h1>
        </header>

        <div className="glass-card animate-fade-in" style={{ maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
          <h2 style={{ marginBottom: '1rem', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ShieldCheck size={24} /> Consentimiento Informado (NOM-004)
          </h2>
          
          <div style={{ 
            backgroundColor: 'var(--bg-app)', 
            padding: '1.5rem', 
            borderRadius: 'var(--radius-md)', 
            marginBottom: '2rem',
            border: '1px solid var(--border-light)',
            maxHeight: '300px',
            overflowY: 'auto',
            fontSize: '0.95rem',
            lineHeight: '1.6',
            color: 'var(--text)'
          }}>
            <p><strong>Aviso de Privacidad y Consentimiento Informado para Tratamiento de Datos Personales en Salud</strong></p>
            <p>Conforme a la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP) y la Norma Oficial Mexicana NOM-004-SSA3-2012 del Expediente Clínico:</p>
            <p>1. El paciente reconoce y acepta que sus datos personales, incluyendo datos sensibles de salud, serán recabados, almacenados y tratados de forma confidencial y segura exclusivamente para fines de atención médica, diagnóstico y tratamiento.</p>
            <p>2. El médico tratante está autorizado para integrar estos datos en el Expediente Clínico Electrónico (ECE).</p>
            <p>3. El paciente tiene derecho a acceder, rectificar o solicitar la cancelación del tratamiento de sus datos (Derechos ARCO), salvo en los casos de conservación obligatoria estipulados por la ley (5 años mínimos para el ECE).</p>
            <p><em>(Este texto es un machote legal de demostración. Al aceptar, el evento se registra de manera inmutable en la bitácora de auditoría).</em></p>
          </div>

          <label style={{ 
            display: 'flex', 
            alignItems: 'flex-start', 
            gap: '1rem', 
            cursor: 'pointer', 
            padding: '1rem',
            backgroundColor: consentAccepted ? 'rgba(0,150,255,0.05)' : 'transparent',
            border: consentAccepted ? '1px solid var(--primary)' : '1px solid var(--border-light)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '2rem',
            transition: 'all 0.2s'
          }}>
            <input 
              type="checkbox" 
              checked={consentAccepted}
              onChange={(e) => setConsentAccepted(e.target.checked)}
              style={{ width: '20px', height: '20px', marginTop: '0.2rem', cursor: 'pointer' }}
            />
            <span>
              <strong>Declaro bajo protesta de decir verdad</strong> que he leído el aviso de privacidad al paciente y que ha otorgado su consentimiento expreso para el tratamiento de su información de salud.
            </span>
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button 
              className="btn btn-primary" 
              onClick={() => createExpedienteMutation.mutate()}
              disabled={!consentAccepted || createExpedienteMutation.isPending}
            >
              {createExpedienteMutation.isPending ? 'Creando y Registrando...' : 'Aceptar y Abrir Expediente'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }} className="no-print">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn btn-outline" style={{ padding: '0.5rem', borderRadius: '12px' }} onClick={() => navigate('/app')}>
            <ArrowLeft size={20} />
          </button>
          <h1 className="font-serif animate-fade-in" style={{ marginBottom: 0, fontSize: '2rem', fontWeight: 600, color: 'var(--text-main)' }}>Expediente Clínico</h1>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-outline no-print" onClick={() => window.print()}>
            <Printer size={20} /> Imprimir / PDF
          </button>
          <button className="btn btn-primary" onClick={() => { setEditingNota(null); setIsSidePanelOpen(true); }}>
            <Plus size={20} /> Nuevo Borrador
          </button>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem', flex: 1 }}>
        {/* Columna Izquierda: Datos del Paciente */}
        <div className="glass-card animate-fade-in" style={{ alignSelf: 'start', padding: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '1.5rem' }}>
            <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'linear-gradient(135deg, rgba(0, 122, 255, 0.1), rgba(88, 86, 214, 0.1))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.75rem', fontWeight: 700, color: 'var(--primary)' }}>
              {paciente?.nombre_completo.charAt(0)}
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{paciente?.nombre_completo}</h3>
              <span className="text-muted" style={{ fontSize: '0.85rem' }}>ID: {expediente.numero_expediente}</span>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <span className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>Demografía</span>
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
                <span style={{ fontWeight: 500 }}>CURP:</span> {paciente?.curp || 'N/A'}
              </div>
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
                <span style={{ fontWeight: 500 }}>Sexo:</span> {paciente?.sexo === 'M' ? 'Masculino' : paciente?.sexo === 'F' ? 'Femenino' : 'Otro'}
              </div>
              <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
                <Calendar size={16} className="text-muted" /> {paciente?.fecha_nacimiento}
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '1rem' }}>
              <span className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>Checklist de Cumplimiento</span>
              <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.9rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {paciente?.domicilio && paciente?.telefono 
                    ? <><ShieldCheck size={16} color="var(--success)" /> <span>Datos demográficos completos</span></> 
                    : <><X size={16} color="var(--error)" /> <span className="text-muted">Faltan datos de contacto</span></>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {notas.some(n => !n.firmada) 
                    ? <><X size={16} color="var(--error)" /> <span className="text-muted">Borradores pendientes</span></> 
                    : <><ShieldCheck size={16} color="var(--success)" /> <span>Sin borradores pendientes</span></>}
                </div>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '1rem' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                 <span className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>Antecedentes (AHF, APP, APNP)</span>
                 <button className="btn btn-outline" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setIsAntecedentesModalOpen(true)}>
                   <Edit3 size={14} style={{ marginRight: '0.3rem' }} /> Editar
                 </button>
               </div>
               <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-md)', marginTop: '0.5rem', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                {expediente.antecedentes ? (
                  <p style={{ margin: 0 }}>{expediente.antecedentes}</p>
                ) : (
                  <p className="text-muted" style={{ margin: 0, fontStyle: 'italic' }}>Sin antecedentes registrados.</p>
                )}
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '1rem', marginTop: '1rem' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                 <span className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>Privacidad y NOM-024</span>
               </div>
               <button 
                 className="btn btn-outline" 
                 style={{ width: '100%', marginTop: '0.75rem', justifyContent: 'center', fontSize: '0.85rem' }}
                 onClick={() => {
                   window.print();
                   showToast("Se ha impreso el formato", "success");
                 }}
               >
                 <ShieldCheck size={16} color="var(--primary)" />
                 Imprimir Formato Físico
               </button>
            </div>
          </div>
        </div>

        {/* Columna Derecha: Historial de Notas */}
        <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s', display: 'flex', flexDirection: 'column', padding: '1.5rem 1.5rem 0 1.5rem', background: 'transparent', boxShadow: 'none', border: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <Activity size={24} color="var(--primary)" />
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Historial Clínico</h3>
          </div>
          
          <div style={{ overflowY: 'auto', flex: 1, paddingRight: '1rem', paddingBottom: '1.5rem' }}>
            {isLoadingNotas ? (
              <div style={{ textAlign: 'center', padding: '2rem' }} className="text-muted">Cargando notas...</div>
            ) : notas.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', border: '2px dashed var(--border-light)', borderRadius: 'var(--radius-md)' }}>
                <p className="text-muted">No hay notas registradas para este expediente.</p>
              </div>
            ) : (
              <div 
                style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}
              >
                {notas.map((nota: Nota) => (
                  <div 
                    key={nota.id}
                    id={`nota-${nota.id}`}
                    className="fade-in"
                    style={{ 
                    border: nota.firmada ? '1px solid var(--border-light)' : '1px solid rgba(0, 122, 255, 0.3)', 
                    borderRadius: '16px', 
                    backgroundColor: 'var(--bg-card)',
                    overflow: 'hidden',
                    boxShadow: 'var(--shadow-sm)',
                    transition: 'transform 0.2s ease, box-shadow 0.2s ease'
                  }}>
                    {/* Note Header */}
                    <div style={{ 
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                      padding: '1.25rem 1.5rem', 
                      backgroundColor: nota.firmada ? '#f8fafc' : 'rgba(0, 122, 255, 0.04)',
                      borderBottom: '1px solid var(--border-light)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        {nota.firmada ? (
                          <div style={{ background: 'rgba(16, 185, 129, 0.15)', padding: '0.6rem', borderRadius: '50%' }}>
                            <Lock size={22} color="var(--success)" />
                          </div>
                        ) : (
                          <div style={{ background: 'var(--primary-light)', padding: '0.6rem', borderRadius: '50%' }}>
                            <Edit3 size={22} color="var(--primary)" />
                          </div>
                        )}
                        <div>
                          <strong style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: nota.firmada ? 'var(--success)' : 'var(--primary)', fontSize: '1.05rem', marginBottom: '0.15rem' }}>
                            {nota.firmada ? 'Documento Firmado Criptográficamente' : 'Borrador'} — {nota.tipo_nota.toUpperCase()}
                          </strong>
                          <span className="text-muted" style={{ fontSize: '0.85rem' }}>
                            {nota.firmada ? `Sellado e inmutable según NOM-024 • ${new Date((nota as any).firmado_en || nota.creado_en).toLocaleString()}` : `Última edición: ${new Date(nota.creado_en).toLocaleString()}`}
                          </span>
                        </div>
                      </div>
                      
                      {!nota.firmada && (
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button 
                            className="btn btn-outline" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
                            onClick={() => { setEditingNota(nota); setIsSidePanelOpen(true); }}
                          >
                            <Edit3 size={14} /> Editar
                          </button>
                          <button 
                            className="btn btn-primary" 
                            style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
                            onClick={() => confirmSign(nota)}
                          >
                            <Lock size={14} /> Firmar y Bloquear
                          </button>
                        </div>
                      )}
                    </div>
                    
                    {/* Note Body */}
                    <div style={{ padding: '1.5rem' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
                        <div>
                          <strong className="text-muted" style={{ display: 'block', marginBottom: '0.25rem' }}>Diagnóstico (CIE-10):</strong>
                          <p>{nota.contenido.diagnosticos?.[0] || 'N/A'}</p>
                        </div>
                        <div style={{ backgroundColor: '#f1f5f9', padding: '0.75rem', borderRadius: 'var(--radius-sm)' }}>
                          <strong className="text-muted" style={{ display: 'block', marginBottom: '0.25rem' }}>Signos Vitales:</strong>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                            <span><strong>FC:</strong> {nota.signos_vitales?.frecuencia_cardiaca} lpm</span>
                            <span><strong>FR:</strong> {nota.signos_vitales?.frecuencia_respiratoria} rpm</span>
                            <span><strong>Temp:</strong> {nota.signos_vitales?.temperatura}°C</span>
                            <span><strong>TA:</strong> {nota.signos_vitales?.tension_arterial}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div>
                        <strong className="text-muted" style={{ display: 'block', marginBottom: '0.25rem' }}>Evolución Clínica:</strong>
                        <p style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', lineHeight: '1.5' }}>
                          {formatContenido(nota.contenido)}
                        </p>
                      </div>
                    </div>

                    {/* Signature Badge */}
                    {nota.firmada && (
                      <div style={{ 
                        marginTop: '1rem', 
                        padding: '1rem', 
                        backgroundColor: '#f0fdf4', 
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid #bbf7d0',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#166534', fontWeight: 500 }}>
                            <ShieldCheck size={16} /> Nota firmada y bloqueada
                          </div>
                          <button 
                            className="btn btn-outline no-print" 
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem', color: '#166534', borderColor: '#bbf7d0' }}
                            onClick={() => window.print()}
                          >
                            <Printer size={14} style={{ marginRight: '0.3rem' }} /> Imprimir
                          </button>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', color: '#14532d' }}>
                          <div>
                            <strong>Médico:</strong> {nota.medico_nombre} <br />
                            <strong>Cédula:</strong> {nota.medico_cedula} <br />
                            <strong>Especialidad:</strong> {nota.medico_especialidad}
                          </div>
                          <div>
                            <strong>Fecha de Firma:</strong> {new Date(nota.firmado_en!).toLocaleString()} <br />
                            <strong>Hash de Contenido:</strong> <span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{nota.firma_hash_contenido?.substring(0, 16)}...</span><br />
                            <strong>Algoritmo:</strong> {nota.firma_algoritmo}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Side Panel for Note Creation */}
      <div style={{
        position: 'fixed',
        top: 0,
        right: isSidePanelOpen ? 0 : '-100%',
        width: '100%',
        maxWidth: '500px',
        height: '100vh',
        backgroundColor: 'var(--bg-card)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderLeft: '1px solid var(--border-light)',
        boxShadow: '-10px 0 30px rgba(0,0,0,0.1)',
        transition: 'right var(--transition-smooth)',
        zIndex: 1000,
        padding: '2rem',
        overflowY: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileSignature size={24} color="var(--primary)"/>
            Nuevo Borrador
          </h2>
          <button className="btn btn-outline" style={{ padding: '0.5rem', border: 'none' }} onClick={() => { setIsSidePanelOpen(false); setEditingNota(null); }}>
            <X size={24} />
          </button>
        </div>

        {!editingNota && hasDraft && (
          <div style={{ backgroundColor: 'var(--primary-light)', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', fontSize: '0.9rem' }}>
              <RefreshCcw size={16} />
              <span>Borrador guardado localmente {draftAge}</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="button" className="btn btn-outline" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem', border: 'none', color: 'var(--error)' }} onClick={clearDraft}>
                Descartar
              </button>
              <button type="button" className="btn btn-primary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={applyDraft}>
                Recuperar
              </button>
            </div>
          </div>
        )}

        <form id="nota-form" onSubmit={handleSubmitNota} onChange={handleFormChange}>
          <h4 style={{ marginBottom: '1rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
            Signos Vitales
            {!editingNota && lastSaveSecondsAgo !== null && (
              <span style={{ fontSize: '0.75rem', fontWeight: 400 }}>
                Guardado hace {lastSaveSecondsAgo}s
              </span>
            )}
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="form-group">
              <label className="form-label">FC (lpm)</label>
              <input type="number" name="fc" className="form-input" required defaultValue={editingNota?.signos_vitales?.frecuencia_cardiaca} />
            </div>
            <div className="form-group">
              <label className="form-label">FR (rpm)</label>
              <input type="number" name="fr" className="form-input" required defaultValue={editingNota?.signos_vitales?.frecuencia_respiratoria} />
            </div>
            <div className="form-group">
              <label className="form-label">Temp (°C)</label>
              <input type="number" step="0.1" name="temp" className="form-input" required defaultValue={editingNota?.signos_vitales?.temperatura} />
            </div>
            <div className="form-group">
              <label className="form-label">TA (ej. 120/80)</label>
              <input type="text" name="ta" className="form-input" placeholder="120/80" required pattern="\d{2,3}/\d{2,3}" title="Ej. 120/80" onInput={(e) => e.currentTarget.value = e.currentTarget.value.replace(/[^\d/]/g, '')} defaultValue={editingNota?.signos_vitales?.tension_arterial} />
            </div>
          </div>

          <h4 style={{ marginBottom: '1rem', color: 'var(--text-muted)' }}>Contenido Clínico</h4>
          <div className="form-group">
            <label className="form-label">Evolución Clínica</label>
            <textarea name="evolucion" className="form-input" rows={4} required minLength={10} placeholder="Describa la evolución..." defaultValue={editingNota?.contenido?.evolucion_y_actualizacion_cuadro}></textarea>
          </div>
          
          <div className="form-group">
            <label className="form-label">Diagnóstico Principal</label>
            <input type="text" name="diagnostico" className="form-input" required minLength={5} defaultValue={editingNota?.contenido?.diagnosticos?.[0]} />
          </div>

          <div className="form-group">
            <label className="form-label">Tratamiento / Plan</label>
            <textarea name="tratamiento" className="form-input" rows={3} required minLength={5} defaultValue={editingNota?.contenido?.tratamiento}></textarea>
          </div>

          <div style={{ marginTop: '3rem', display: 'flex', gap: '1rem' }}>
            <button type="button" className="btn btn-outline" style={{ flex: 1 }} onClick={() => setIsSidePanelOpen(false)}>Cancelar</button>
            <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={draftNotaMutation.isPending || updateNotaMutation.isPending}>
              {draftNotaMutation.isPending || updateNotaMutation.isPending ? 'Guardando...' : (editingNota ? 'Actualizar Borrador' : 'Guardar Borrador')}
            </button>
          </div>
        </form>
      </div>
      
      {/* Backdrop for Side Panel */}
      {isSidePanelOpen && (
        <div 
          style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', backgroundColor: 'rgba(0,0,0,0.2)', zIndex: 999 }}
          onClick={() => setIsSidePanelOpen(false)}
        />
      )}

      {/* Sign Confirmation Modal */}
      <Modal
        isOpen={isSignModalOpen}
        onClose={() => setIsSignModalOpen(false)}
        title="Firma Electrónica NOM-004"
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setIsSignModalOpen(false)}>
              Revisar de nuevo
            </button>
            <button 
              className="btn btn-primary" 
              onClick={() => notaToSign && signNotaMutation.mutate(notaToSign.id)}
              disabled={signNotaMutation.isPending}
            >
              {signNotaMutation.isPending ? 'Firmando y Bloqueando...' : 'Firmar y Bloquear'}
            </button>
          </>
        }
      >
        <div style={{ backgroundColor: 'var(--primary-light)', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem', fontSize: '0.9rem', color: 'var(--primary)' }}>
          <ShieldCheck size={20} style={{ marginBottom: '0.5rem' }} />
          <p>Al firmar esta nota médica, se generará una firma criptográfica ECDSA vinculada a su identidad y al hash exacto del contenido de la nota.</p>
        </div>
        <p style={{ marginBottom: '1rem', fontWeight: 500 }}>
          De acuerdo con la NOM-004-SSA3-2012:
        </p>
        <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          <li style={{ marginBottom: '0.5rem' }}>Las notas médicas firmadas son inmutables y no podrán ser alteradas ni eliminadas.</li>
          <li>Cualquier corrección posterior deberá realizarse mediante una nota de adenda separada.</li>
        </ul>
        <p style={{ fontSize: '0.9rem' }}>
          ¿Confirma que la información clínica capturada es correcta y final?
        </p>
      </Modal>

      {/* Antecedentes Modal */}
      <Modal
        isOpen={isAntecedentesModalOpen}
        onClose={() => setIsAntecedentesModalOpen(false)}
        title="Editar Antecedentes Médicos"
      >
        <form onSubmit={handleUpdateAntecedentes}>
          <div className="form-group" style={{ marginBottom: '1.5rem' }}>
            <label className="form-label text-muted">Incluya Antecedentes Heredofamiliares, Personales Patológicos, No Patológicos y Alergias (formato libre).</label>
            <textarea 
              name="antecedentes" 
              className="form-input" 
              rows={8} 
              defaultValue={expediente?.antecedentes || ''}
              placeholder="Ej. Padre finado por IAM. Diabetes mellitus tipo 2 diagnosticada hace 5 años. Alérgico a penicilina."
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
            <button type="button" className="btn btn-outline" onClick={() => setIsAntecedentesModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={updateAntecedentesMutation.isPending}>
              {updateAntecedentesMutation.isPending ? 'Guardando...' : 'Guardar Antecedentes'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
