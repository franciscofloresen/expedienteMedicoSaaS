/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, type FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, X, FileSignature, Edit3, Lock, ShieldCheck, Printer, Check, Droplets, AlertTriangle, CalendarClock, ClipboardList, MessageCircle } from 'lucide-react';
import { consentimientosApi, expedientesApi, favoritosApi, messagesApi, notasApi, pacientesApi, plantillasNotaApi, recetasApi } from '../services/api';
import type { Nota, NotaCreate, NotaDiagnosticoCie10, FavoritoKind, MedicoFavoritoCreate, NotaPlantilla } from '../types';
import { useToast } from '../hooks/useToast';
import { useServerAutosave } from '../hooks/useServerAutosave';
import { useServerHealth } from '../hooks/useServerHealth';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import PatientIdentityBanner from '../components/PatientIdentityBanner';
import FavoritesPicker from '../components/FavoritesPicker';
import NoteTemplatePicker from '../components/NoteTemplatePicker';
import LongitudinalSummary from '../components/LongitudinalSummary';
import ProcedimientosPanel from '../components/ProcedimientosPanel';
import FotografiasPanel from '../components/FotografiasPanel';
import { buildCopyForwardDraft, type CopyForwardDraft } from '../utils/copyForward';
import { buildLongitudinalSummary } from '../utils/longitudinalSummary';
import { useEffect } from 'react';
import Modal from '../components/Modal';
import Cie10DiagnosisSelector from '../components/Cie10DiagnosisSelector';
import ClinicalFiles from '../components/ClinicalFiles';
import { SignaturePad } from '../components/SignaturePad';
import { useReverification } from '@clerk/react';

type TabKey = 'resumen' | 'longitudinal' | 'consultas' | 'historia' | 'procedimientos' | 'archivos' | 'consentimientos';

function initials(nombre?: string): string {
  if (!nombre) return '';
  const parts = nombre.trim().split(/\s+/);
  return ((parts[0]?.charAt(0) ?? '') + (parts[1]?.charAt(0) ?? '')).toUpperCase();
}

function EmptyNotas({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="empty-state glass-card">
      <svg className="empty-illustration" width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="34" y="10" width="52" height="68" rx="6" stroke="var(--color-border)" strokeWidth="2" fill="var(--color-surface-2)" />
        <path d="M44 28h32M44 40h32M44 52h20" stroke="var(--color-muted)" strokeWidth="2" strokeLinecap="round" opacity="0.5" />
        <circle cx="86" cy="66" r="14" fill="var(--color-primary-tint)" stroke="var(--color-primary)" strokeWidth="2" />
        <path d="M86 60v12M80 66h12" stroke="var(--color-primary)" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <div className="empty-state-title">Sin consultas registradas</div>
      <p className="empty-state-hint">Crea la primera nota de evolución para este expediente.</p>
      <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={onCreate}>
        <Plus size={16} /> Nueva consulta
      </button>
    </div>
  );
}

function friendlyActionError(error: unknown, fallback: string): string {
  const maybe = error as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = maybe.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim() && !detail.includes('Internal Server Error')) return detail;
  if (typeof maybe.message === 'string' && maybe.message.trim() && !maybe.message.includes('500')) return maybe.message;
  return fallback;
}

export default function Expediente() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { showToast } = useToast();
  // Fase 10: while the server can't confirm writes, signing is blocked — a signed
  // note is immutable evidence and must never be produced over data we can't persist.
  const { isDegraded } = useServerHealth();
  const signNotaWithReauthentication = useReverification(notasApi.firmar);
  const signRecetaWithReauthentication = useReverification(recetasApi.firmar);
  const signConsentWithReauthentication = useReverification(consentimientosApi.firmarMedico);
  const revokeConsentWithReauthentication = useReverification(consentimientosApi.revocar);

  const [activeTab, setActiveTab] = useState<TabKey>(window.location.hash ? 'consultas' : 'resumen');

  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false);
  const [editingNota, setEditingNota] = useState<Nota | null>(null);
  const [diagnosticosCie10, setDiagnosticosCie10] = useState<NotaDiagnosticoCie10[]>([]);

  const [isSignModalOpen, setIsSignModalOpen] = useState(false);
  const [notaToSign, setNotaToSign] = useState<Nota | null>(null);

  const [isAntecedentesModalOpen, setIsAntecedentesModalOpen] = useState(false);

  // Receta state
  const [isRecetaModalOpen, setIsRecetaModalOpen] = useState(false);
  const [activeNotaForReceta, setActiveNotaForReceta] = useState<Nota | null>(null);
  const [recetaText, setRecetaText] = useState('');
  const [isConsentModalOpen, setIsConsentModalOpen] = useState(false);
  const [selectedConsentTemplate, setSelectedConsentTemplate] = useState('estetico_no_quirurgico');
  const [consentSignerType, setConsentSignerType] = useState<'paciente' | 'representante' | 'tutor'>('paciente');
  const [consentSignature, setConsentSignature] = useState('');
  const [witnessSignatures, setWitnessSignatures] = useState<string[]>([]);
  const [credentialByConsent, setCredentialByConsent] = useState<Record<string, string>>({});

  // Fase 13: server autosave for existing drafts (no PHI in localStorage). A NEW
  // note can't be autosaved because NOM-004 requires vitals + diagnosis before the
  // note exists; it persists only on "Guardar borrador".
  const [formSnapshot, setFormSnapshot] = useState<Record<string, unknown> | null>(null);
  const autosave = useServerAutosave({
    data: editingNota ? formSnapshot : null,
    enabled: Boolean(editingNota) && isSidePanelOpen && !isDegraded,
    save: async (snap) => {
      if (!editingNota) return;
      await notasApi.update(editingNota.id, snap as Partial<NotaCreate>);
    },
  });

  // Fase 13: copy-from-previous-consult. seedDraft holds the narrative fields
  // carried into a NEW draft; formKey remounts the uncontrolled form so the seed
  // (and edit defaults) actually apply on open.
  const [seedDraft, setSeedDraft] = useState<CopyForwardDraft | null>(null);
  const [formKey, setFormKey] = useState(0);

  const openNoteEditor = (opts?: { nota?: Nota; seed?: CopyForwardDraft }) => {
    setEditingNota(opts?.nota ?? null);
    setSeedDraft(opts?.seed ?? null);
    setDiagnosticosCie10(opts?.nota?.diagnosticos_cie10 ?? []);
    setFormSnapshot(null);
    setFormKey((k) => k + 1);
    setIsSidePanelOpen(true);
  };
  const closeNoteEditor = () => {
    setIsSidePanelOpen(false);
    setEditingNota(null);
    setDiagnosticosCie10([]);
    setSeedDraft(null);
  };

  // Fase 13 keyboard shortcuts (keyboard-only documentation): Ctrl/Cmd+S (or
  // Ctrl/Cmd+Enter) saves the draft via the form's own validation; Esc closes.
  const submitNoteForm = () =>
    (document.getElementById('nota-form') as HTMLFormElement | null)?.requestSubmit();
  useKeyboardShortcuts(
    [
      { key: 's', ctrlOrMeta: true, handler: submitNoteForm },
      { key: 'Enter', ctrlOrMeta: true, handler: submitNoteForm },
      { key: 'Escape', handler: closeNoteEditor },
    ],
    isSidePanelOpen,
  );

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

  const { data: consentTemplates = [] } = useQuery({
    queryKey: ['consentimiento-templates'],
    queryFn: () => consentimientosApi.templates(),
  });

  const { data: signingCredentials = [] } = useQuery({
    queryKey: ['consentimiento-credenciales-firma'],
    queryFn: () => consentimientosApi.credencialesFirma(),
  });

  const { data: consentimientos = [] } = useQuery({
    queryKey: ['consentimientos', expediente?.id],
    queryFn: () => consentimientosApi.getByExpedienteId(expediente?.id as string),
    enabled: !!expediente?.id,
  });

  const { data: messageLogs = [] } = useQuery({
    queryKey: ['messageLogs', id],
    queryFn: () => messagesApi.getByPacienteId(id!),
    enabled: !!id,
  });

  const activeConsentTemplate = consentTemplates.find((template: any) => template.key === selectedConsentTemplate);
  const requiredWitnesses = Number(activeConsentTemplate?.firmas_requeridas?.testigos || 0);

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
      showToast("Expediente creado. Ya puedes capturar la primera nota médica.", "success");
    },
    onError: (err: any) => {
      showToast(
        friendlyActionError(err, "No pudimos crear el expediente. Revisa tu conexión e inténtalo de nuevo."),
        "error"
      );
    }
  });

  const updateAntecedentesMutation = useMutation({
    mutationFn: (antecedentes: string) => expedientesApi.updateAntecedentes(expediente!.id, antecedentes),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['expediente', id] });
      setIsAntecedentesModalOpen(false);
      showToast("Antecedentes médicos actualizados.", "success");
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos guardar los antecedentes. Inténtalo de nuevo."),
        "error"
      );
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
      setDiagnosticosCie10([]);
      setFormSnapshot(null);
      setSeedDraft(null);
      showToast("Borrador de nota médica guardado.", "success");
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos guardar el borrador. Revisa los campos obligatorios e inténtalo de nuevo."),
        "error"
      );
    }
  });

  const updateNotaMutation = useMutation({
    mutationFn: (payload: { id: string, data: Partial<NotaCreate> }) => notasApi.update(payload.id, payload.data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSidePanelOpen(false);
      setEditingNota(null);
      setDiagnosticosCie10([]);
      setFormSnapshot(null);
      setSeedDraft(null);
      showToast("Borrador de nota médica actualizado.", "success");
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos actualizar el borrador. Inténtalo de nuevo."),
        "error"
      );
    }
  });

  const signNotaMutation = useMutation({
    mutationFn: (notaId: string) => signNotaWithReauthentication(notaId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['notas', expediente?.id] });
      setIsSignModalOpen(false);
      setNotaToSign(null);
      showToast("Nota médica firmada. El documento legal ya está disponible.", "success");
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos firmar la nota. Revisa tu sesión e inténtalo de nuevo."),
        "error"
      );
      setIsSignModalOpen(false);
    }
  });

  const handleSubmitNota = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!expediente) return;
    if (!editingNota && diagnosticosCie10.length === 0) {
      showToast("Agrega al menos un diagnóstico CIE-10 antes de guardar la nota.", "error");
      return;
    }

    const formData = new FormData(e.currentTarget);

    const contenido = {};
    const motivo_consulta = formData.get('motivo_consulta') as string;
    const exploracion_fisica = formData.get('exploracion_fisica') as string;
    const plan_tratamiento = formData.get('plan_tratamiento') as string;

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
          tratamiento: plan_tratamiento,
          motivo_consulta,
          exploracion_fisica,
          plan_tratamiento,
        }
      });
    } else {
      const diagnosticos_cie10 = diagnosticosCie10.map((item, orden) => ({
        code: item.code,
        es_principal: item.es_principal,
        certeza: item.certeza,
        orden,
      }));
      const principal = diagnosticosCie10.find((item) => item.es_principal);
      draftNotaMutation.mutate({
        expediente_id: expediente.id,
        tipo_nota: 'evolucion',
        contenido,
        signos_vitales,
        diagnosticos: [formData.get('diagnostico') as string],
        tratamiento: plan_tratamiento,
        motivo_consulta,
        exploracion_fisica,
        plan_tratamiento,
        // Preserve the principal code in the legacy snapshot while the structured
        // payload carries every diagnosis with certainty and ordering.
        diagnostico_cie10: principal
          ? `${principal.code} - ${principal.description || ''}`.trim()
          : undefined,
        diagnosticos_cie10,
      });
    }
  };

  // Snapshot the editable fields as a NotaUpdate payload so server autosave can
  // persist an existing draft. Mirrors the updateNotaMutation payload.
  const buildNoteSnapshot = (form: HTMLFormElement): Record<string, unknown> => {
    const fd = new FormData(form);
    return {
      contenido: {},
      signos_vitales: {
        frecuencia_cardiaca: Number(fd.get('fc')),
        frecuencia_respiratoria: Number(fd.get('fr')),
        temperatura: Number(fd.get('temp')),
        tension_arterial: fd.get('ta') as string,
      },
      diagnosticos: [fd.get('diagnostico') as string],
      tratamiento: fd.get('plan_tratamiento') as string,
      motivo_consulta: fd.get('motivo_consulta') as string,
      exploracion_fisica: fd.get('exploracion_fisica') as string,
      plan_tratamiento: fd.get('plan_tratamiento') as string,
    };
  };

  const handleFormChange = (e: FormEvent<HTMLFormElement>) => {
    setFormSnapshot(buildNoteSnapshot(e.currentTarget));
  };

  const handleCie10Change = (next: NotaDiagnosticoCie10[]) => {
    setDiagnosticosCie10(next);
  };

  const confirmSign = (nota: Nota) => {
    setNotaToSign(nota);
    setIsSignModalOpen(true);
  };

  const openWhatsApp = (message: string) => {
    const rawPhone = paciente?.telefono?.replace(/\D/g, '');
    if (!rawPhone) {
      showToast("Este paciente no tiene teléfono registrado para abrir WhatsApp.", "error");
      return;
    }
    window.open(`https://wa.me/${rawPhone}?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  };

  const logWhatsApp = async (message: string, template_key: string, resource?: { type: string; id: string }) => {
    if (!paciente?.id) return;
    await messagesApi.logWhatsAppManual({
      paciente_id: paciente.id,
      resource_type: resource?.type,
      resource_id: resource?.id,
      template_key,
      message_preview: message,
    });
    client.invalidateQueries({ queryKey: ['messageLogs', id] });
    showToast("Envío manual por WhatsApp registrado en la bitácora.", "success");
  };

  const sendPatientWhatsApp = async () => {
    const message = `Hola ${paciente?.nombre_completo || ''}, te escribe tu consultorio para dar seguimiento a tu atención médica.`;
    openWhatsApp(message);
    await logWhatsApp(message, 'mensaje_paciente');
  };

  const sendNoteVerificationWhatsApp = async (nota: Nota) => {
    const preview = await notasApi.legalPreview(nota.id);
    const message = `Hola ${paciente?.nombre_completo || ''}, puedes verificar tu documento clínico aquí: ${preview.firma?.verification_url}`;
    openWhatsApp(message);
    await logWhatsApp(message, 'link_verificacion_nota', { type: 'nota', id: nota.id });
  };

  const createRecetaMutation = useMutation({
    mutationFn: async (data: { nota_id: string; texto: string }) => {
      const receta = await recetasApi.create({
        nota_id: data.nota_id,
        medicamentos: [{ descripcion: data.texto }],
        indicaciones_generales: "Indicaciones incluidas en receta"
      });
      return signRecetaWithReauthentication(receta.id);
    },
    onSuccess: async (receta) => {
      setIsRecetaModalOpen(false);
      setRecetaText('');
      showToast("Receta generada y lista para imprimir.", "success");
      navigate(`/app/documentos/receta/${receta.id}/print`);
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos generar la receta. Revisa el contenido e inténtalo de nuevo."),
        "error"
      );
    }
  });

  const handlePrintReceta = () => {
    if (!activeNotaForReceta) return;
    createRecetaMutation.mutate({ nota_id: activeNotaForReceta.id, texto: recetaText });
  };

  // Fase 13: doctor's prescription favorites — one-click insertion + save-current.
  const { data: recetaFavoritos = [] } = useQuery({
    queryKey: ['favoritos', 'receta'],
    queryFn: () => favoritosApi.list('receta'),
  });
  const saveRecetaFavoritoMutation = useMutation({
    mutationFn: (data: { label: string; texto: string }) =>
      favoritosApi.create({ kind: 'receta', label: data.label, texto: data.texto }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['favoritos', 'receta'] });
      showToast('Receta guardada en tus favoritos.', 'success');
    },
    onError: (error: unknown) =>
      showToast(friendlyActionError(error, 'No se pudo guardar el favorito.'), 'error'),
  });
  const handleSaveRecetaFavorito = () => {
    const texto = recetaText.trim();
    if (!texto) return;
    const label = window.prompt('Nombre corto para este favorito:', texto.slice(0, 40));
    if (!label || !label.trim()) return;
    saveRecetaFavoritoMutation.mutate({ label: label.trim(), texto });
  };

  // Fase 13: favoritos inside the note editor (diagnosis + plan). Fields are
  // uncontrolled, so insertion writes to the DOM value and re-syncs the autosave
  // snapshot. Reused for save-current.
  const { data: diagnosticoFavoritos = [] } = useQuery({
    queryKey: ['favoritos', 'diagnostico'],
    queryFn: () => favoritosApi.list('diagnostico'),
  });
  const { data: planFavoritos = [] } = useQuery({
    queryKey: ['favoritos', 'plan'],
    queryFn: () => favoritosApi.list('plan'),
  });
  const createFavoritoMutation = useMutation({
    mutationFn: (data: MedicoFavoritoCreate) => favoritosApi.create(data),
    onSuccess: async (_res, vars) => {
      await client.invalidateQueries({ queryKey: ['favoritos', vars.kind] });
      showToast('Guardado en tus favoritos.', 'success');
    },
    onError: (error: unknown) =>
      showToast(friendlyActionError(error, 'No se pudo guardar el favorito.'), 'error'),
  });

  const readNoteField = (name: string): string => {
    const form = document.getElementById('nota-form') as HTMLFormElement | null;
    const el = form?.elements.namedItem(name) as HTMLInputElement | HTMLTextAreaElement | undefined;
    return el?.value ?? '';
  };
  const insertIntoNoteField = (name: string, texto: string) => {
    const form = document.getElementById('nota-form') as HTMLFormElement | null;
    const el = form?.elements.namedItem(name) as HTMLInputElement | HTMLTextAreaElement | undefined;
    if (!form || !el) return;
    el.value = el.value ? `${el.value}\n${texto}` : texto;
    el.focus();
    setFormSnapshot(buildNoteSnapshot(form));
  };
  const promptSaveNoteFavorito = (kind: FavoritoKind, name: string) => {
    const texto = readNoteField(name).trim();
    if (!texto) return;
    const label = window.prompt('Nombre corto para este favorito:', texto.slice(0, 40));
    if (!label || !label.trim()) return;
    createFavoritoMutation.mutate({ kind, label: label.trim(), texto });
  };

  // Fase 13: configurable note templates (versioned JSON of field pre-fills).
  const { data: notaPlantillas = [] } = useQuery({
    queryKey: ['plantillas-nota'],
    queryFn: () => plantillasNotaApi.list(),
  });
  const createPlantillaMutation = useMutation({
    mutationFn: (data: { nombre: string; campos: Record<string, string> }) =>
      plantillasNotaApi.create(data),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['plantillas-nota'] });
      showToast('Plantilla guardada.', 'success');
    },
    onError: (error: unknown) =>
      showToast(friendlyActionError(error, 'No se pudo guardar la plantilla.'), 'error'),
  });

  const applyNoteTemplate = (plantilla: NotaPlantilla) => {
    Object.entries(plantilla.campos).forEach(([field, texto]) => {
      if (texto) insertIntoNoteField(field, texto);
    });
    showToast(`Plantilla "${plantilla.nombre}" aplicada. Revisa y completa.`, 'info');
  };
  const handleSaveNoteTemplate = () => {
    const campos: Record<string, string> = {};
    for (const field of ['motivo_consulta', 'exploracion_fisica', 'plan_tratamiento', 'diagnostico']) {
      const value = readNoteField(field).trim();
      if (value) campos[field] = value;
    }
    if (Object.keys(campos).length === 0) return;
    const nombre = window.prompt('Nombre de la plantilla:');
    if (!nombre || !nombre.trim()) return;
    createPlantillaMutation.mutate({ nombre: nombre.trim(), campos });
  };
  const noteHasContent = () =>
    ['motivo_consulta', 'exploracion_fisica', 'plan_tratamiento', 'diagnostico'].some(
      (f) => readNoteField(f).trim(),
    );

  const createConsentimientoMutation = useMutation({
    mutationFn: async (form: FormData) => {
      const created = await consentimientosApi.create({
        paciente_id: paciente!.id,
        expediente_id: expediente!.id,
        template_key: selectedConsentTemplate,
        procedimiento: form.get('procedimiento'),
        riesgos_principales: form.get('riesgos_principales') || undefined,
      });
      await consentimientosApi.firmarPaciente(created.id, {
        nombre_completo: form.get('nombre_paciente') || paciente!.nombre_completo,
        firma_paciente_base64: consentSignature,
        aceptado: form.get('aceptado') === 'on',
        tipo_firmante: consentSignerType,
        relacion_paciente: form.get('relacion_paciente') || undefined,
        motivo_representacion: form.get('motivo_representacion') || undefined,
        testigos: Array.from({ length: requiredWitnesses }, (_, index) => ({
          nombre_completo: String(form.get(`testigo_${index + 1}_nombre`) || ''),
          firma_base64: witnessSignatures[index] || '',
        })),
      });
      return created;
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['consentimientos', expediente?.id] });
      setIsConsentModalOpen(false);
      setConsentSignature('');
      setWitnessSignatures([]);
      setConsentSignerType('paciente');
      showToast("Consentimiento creado y firmado por el paciente.", "success");
    },
    onError: (error: unknown) => {
      showToast(
        friendlyActionError(error, "No pudimos crear el consentimiento. Revisa los campos obligatorios e inténtalo de nuevo."),
        "error"
      );
    }
  });

  if (isLoadingExpediente) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <span>Cargando expediente clínico…</span>
      </div>
    );
  }

  // ── Consent / create expediente screen ──────────────────────
  if (!expediente) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
          <button className="btn btn-outline" style={{ padding: '0.5rem' }} onClick={() => navigate('/app')} aria-label="Volver">
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="page-title" style={{ marginBottom: 0 }}>Crear expediente</h1>
            <p className="page-subtitle">{paciente?.nombre_completo}</p>
          </div>
        </header>

        <div className="glass-card fade-in" style={{ maxWidth: '760px', margin: '0 auto', width: '100%', padding: '2rem' }}>
          <h2 style={{ marginBottom: '1rem', color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.15rem' }}>
            <ShieldCheck size={20} /> Consentimiento informado (NOM-004)
          </h2>

          <div style={{
            backgroundColor: 'var(--color-bg)',
            padding: '1.25rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1.5rem',
            border: '1px solid var(--color-border)',
            maxHeight: '300px',
            overflowY: 'auto',
            fontSize: '0.9rem',
            lineHeight: 1.7,
            color: 'var(--color-text)'
          }}>
            <p><strong>Aviso de Privacidad y Consentimiento Informado para Tratamiento de Datos Personales en Salud</strong></p>
            <p>Conforme a la Ley Federal de Protección de Datos Personales en Posesión de los Particulares (LFPDPPP) y la Norma Oficial Mexicana NOM-004-SSA3-2012 del Expediente Clínico:</p>
            <p>1. El paciente reconoce y acepta que sus datos personales, incluyendo datos sensibles de salud, serán recabados, almacenados y tratados de forma confidencial y segura exclusivamente para fines de atención médica, diagnóstico y tratamiento.</p>
            <p>2. El médico tratante está autorizado para integrar estos datos en el Expediente Clínico Electrónico (ECE).</p>
            <p>3. El paciente tiene derecho a acceder, rectificar o solicitar la cancelación del tratamiento de sus datos (Derechos ARCO), salvo en los casos de conservación obligatoria estipulados por la ley (5 años mínimos para el ECE).</p>
            <p><em>Este texto es una plantilla de demostración. Al aceptar, el evento se registra en la bitácora de actividad.</em></p>
          </div>

          <label style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.9rem',
            cursor: 'pointer',
            padding: '1rem',
            backgroundColor: consentAccepted ? 'var(--color-primary-tint)' : 'transparent',
            border: consentAccepted ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1.5rem',
            fontSize: '0.9rem',
            transition: 'border-color 0.15s ease, background-color 0.15s ease'
          }}>
            <input
              type="checkbox"
              checked={consentAccepted}
              onChange={(e) => setConsentAccepted(e.target.checked)}
              style={{ width: '18px', height: '18px', marginTop: '0.2rem', cursor: 'pointer', flexShrink: 0 }}
            />
            <span>
              <strong>Confirmo que el paciente recibió el aviso de privacidad</strong> y otorgó consentimiento expreso para el tratamiento de su información de salud.
            </span>
          </label>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn btn-primary"
              onClick={() => createExpedienteMutation.mutate()}
              disabled={!consentAccepted || createExpedienteMutation.isPending}
            >
              {createExpedienteMutation.isPending ? 'Creando y registrando…' : 'Aceptar y abrir expediente'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const lastVisit = notas.length > 0
    ? new Date(Math.max(...notas.map((n: Nota) => new Date(n.creado_en).getTime())))
    : null;

  const drafts = notas.filter((n: Nota) => !n.firmada);

  // ── Main expediente view ────────────────────────────────────
  return (
    <div style={{ position: 'relative', minHeight: '100%', display: 'flex', flexDirection: 'column' }}>
      <header className="page-header no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
          <button className="btn btn-outline" style={{ padding: '0.5rem' }} onClick={() => navigate('/app')} aria-label="Volver a pacientes">
            <ArrowLeft size={18} />
          </button>
          <div className="avatar avatar-lg">{initials(paciente?.nombre_completo)}</div>
          <div style={{ minWidth: 0 }}>
            <h1 className="page-title" style={{ marginBottom: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {paciente?.nombre_completo}
            </h1>
            <p className="page-subtitle mono">Expediente {expediente.numero_expediente}</p>
          </div>
        </div>
        <div className="page-header-actions" style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-outline no-print" onClick={sendPatientWhatsApp}>
            <MessageCircle size={16} /> WhatsApp
          </button>
          <button className="btn btn-outline no-print" onClick={() => window.print()}>
            <Printer size={16} /> Imprimir / PDF
          </button>
          <button className="btn btn-primary" onClick={() => openNoteEditor()}>
            <Plus size={16} /> Nueva consulta
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="tab-bar no-print" role="tablist">
        <button role="tab" aria-selected={activeTab === 'resumen'} className={activeTab === 'resumen' ? 'tab active' : 'tab'} onClick={() => setActiveTab('resumen')}>
          Resumen
        </button>
        <button role="tab" aria-selected={activeTab === 'longitudinal'} className={activeTab === 'longitudinal' ? 'tab active' : 'tab'} onClick={() => setActiveTab('longitudinal')}>
          Longitudinal
        </button>
        <button role="tab" aria-selected={activeTab === 'consultas'} className={activeTab === 'consultas' ? 'tab active' : 'tab'} onClick={() => setActiveTab('consultas')}>
          Consultas <span className="tab-count">{notas.length}</span>
        </button>
        <button role="tab" aria-selected={activeTab === 'historia'} className={activeTab === 'historia' ? 'tab active' : 'tab'} onClick={() => setActiveTab('historia')}>
          Historia clínica
        </button>
        <button role="tab" aria-selected={activeTab === 'procedimientos'} className={activeTab === 'procedimientos' ? 'tab active' : 'tab'} onClick={() => setActiveTab('procedimientos')}>
          Procedimientos
        </button>
        <button role="tab" aria-selected={activeTab === 'archivos'} className={activeTab === 'archivos' ? 'tab active' : 'tab'} onClick={() => setActiveTab('archivos')}>
          Archivos
        </button>
        <button role="tab" aria-selected={activeTab === 'consentimientos'} className={activeTab === 'consentimientos' ? 'tab active' : 'tab'} onClick={() => setActiveTab('consentimientos')}>
          Consentimientos <span className="tab-count">{consentimientos.length}</span>
        </button>
      </div>

      {/* ── Tab: Resumen ── */}
      {activeTab === 'resumen' && (
        <div className={isRecetaModalOpen ? 'no-print fade-in' : 'fade-in'}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="stat-card">
              <div className="stat-icon">
                <Droplets size={20} />
              </div>
              <div>
                <span className="overline">Tipo de sangre</span>
                <div className="stat-value">{paciente?.tipo_sangre || '—'}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon" style={paciente?.alergias ? { background: 'var(--color-danger-tint)', color: 'var(--color-danger)' } : undefined}>
                <AlertTriangle size={20} />
              </div>
              <div>
                <span className="overline">Alergias</span>
                <div style={{ fontWeight: 600, fontSize: '0.95rem', color: paciente?.alergias ? 'var(--color-danger)' : 'var(--color-text)' }}>
                  {paciente?.alergias || 'Ninguna registrada'}
                </div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <CalendarClock size={20} />
              </div>
              <div>
                <span className="overline">Última consulta</span>
                <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                  {lastVisit ? lastVisit.toLocaleDateString() : 'Sin consultas'}
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
            <div className="glass-card">
              <span className="overline" style={{ marginBottom: '0.75rem' }}>Demografía</span>
              <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.45rem 1rem', fontSize: '0.9rem', margin: 0 }}>
                <dt style={{ color: 'var(--color-muted)' }}>CURP</dt>
                <dd className="mono" style={{ margin: 0 }}>{paciente?.curp || 'N/A'}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Sexo</dt>
                <dd style={{ margin: 0 }}>{paciente?.sexo === 'M' ? 'Masculino' : paciente?.sexo === 'F' ? 'Femenino' : 'Otro'}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Nacimiento</dt>
                <dd style={{ margin: 0 }}>{paciente?.fecha_nacimiento}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Teléfono</dt>
                <dd style={{ margin: 0 }}>{paciente?.telefono || 'No reg.'}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Emergencia</dt>
                <dd style={{ margin: 0 }}>
                  {paciente?.contacto_emergencia || 'No reg.'} {paciente?.telefono_emergencia ? `(${paciente.telefono_emergencia})` : ''}
                </dd>
              </dl>
            </div>

            <div className="glass-card">
              <span className="overline" style={{ marginBottom: '0.75rem' }}>Checklist de cumplimiento</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', fontSize: '0.9rem', marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {paciente?.domicilio && paciente?.telefono
                    ? <><Check size={15} color="var(--color-success)" /> <span>Datos demográficos completos</span></>
                    : <><X size={15} color="var(--color-danger)" /> <span className="text-muted">Faltan datos de contacto</span></>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {drafts.length > 0
                    ? <><X size={15} color="var(--color-danger)" /> <span className="text-muted">{drafts.length} borrador{drafts.length > 1 ? 'es' : ''} pendiente{drafts.length > 1 ? 's' : ''} de firma</span></>
                    : <><Check size={15} color="var(--color-success)" /> <span>Sin borradores pendientes</span></>}
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--color-border)', marginTop: '1rem', paddingTop: '1rem' }}>
                <span className="overline" style={{ marginBottom: '0.5rem' }}>Privacidad y NOM-024</span>
                <button
                  className="btn btn-outline"
                  style={{ width: '100%', marginTop: '0.5rem' }}
                  onClick={() => {
                    window.print();
                    showToast("Se ha impreso el formato", "success");
                  }}
                >
                  <ShieldCheck size={15} />
                  Imprimir formato físico
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Longitudinal ── */}
      {activeTab === 'longitudinal' && (
        <LongitudinalSummary
          summary={buildLongitudinalSummary(paciente, notas, consentimientos)}
        />
      )}

      {/* ── Tab: Procedimientos ── */}
      {activeTab === 'procedimientos' && id && <ProcedimientosPanel pacienteId={id} />}

      {/* ── Tab: Consultas ── */}
      {activeTab === 'consultas' && (
        <div className={isRecetaModalOpen ? 'no-print fade-in' : 'fade-in'}>
          {isLoadingNotas ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem 0' }}>
              <div className="spinner" />
            </div>
          ) : notas.length === 0 ? (
            <EmptyNotas onCreate={() => openNoteEditor()} />
          ) : (
            <div className="timeline">
              {notas.map((nota: Nota) => (
                <div key={nota.id} className={nota.firmada ? 'timeline-item signed' : 'timeline-item'}>
                  <div
                    id={`nota-${nota.id}`}
                    className={nota.firmada ? 'note-card fade-in' : 'note-card draft fade-in'}
                  >
                    {/* Note header */}
                    <div className="note-card-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
                        {nota.firmada ? (
                          <span className="badge badge-gold"><Lock size={11} /> Firmada</span>
                        ) : (
                          <span className="badge badge-draft"><Edit3 size={11} /> Borrador</span>
                        )}
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.9rem', textTransform: 'capitalize' }}>
                            {nota.tipo_nota}
                          </div>
                          <div className="text-muted" style={{ fontSize: '0.78rem' }}>
                            {nota.firmada
                            ? `Firmada digitalmente · ${new Date((nota as any).firmado_en || nota.creado_en).toLocaleString()}`
                              : `Última edición: ${new Date(nota.creado_en).toLocaleString()}`}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          className="btn btn-outline"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                          onClick={() => openNoteEditor({ seed: buildCopyForwardDraft(nota) })}
                          title="Iniciar una nueva consulta con el motivo y plan de ésta (revisables)"
                        >
                          <ClipboardList size={13} /> Copiar a nueva
                        </button>
                        {!nota.firmada && (
                          <>
                            <button
                              className="btn btn-outline"
                              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                              onClick={() => openNoteEditor({ nota })}
                            >
                              <Edit3 size={13} /> Editar
                            </button>
                            <button
                              className="btn btn-gold"
                              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                              onClick={() => confirmSign(nota)}
                            >
                              <Lock size={13} /> Firmar nota
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Note body */}
                    <div className="note-card-body">
                      {nota.signos_vitales && (
                        <div className="vitals-strip">
                          <div>
                            <span className="vital-label">FC</span>
                            <span className="vital-value">{nota.signos_vitales.frecuencia_cardiaca ?? '—'} <small>lpm</small></span>
                          </div>
                          <div>
                            <span className="vital-label">FR</span>
                            <span className="vital-value">{nota.signos_vitales.frecuencia_respiratoria ?? '—'} <small>rpm</small></span>
                          </div>
                          <div>
                            <span className="vital-label">Temp</span>
                            <span className="vital-value">{nota.signos_vitales.temperatura ?? '—'}<small>°C</small></span>
                          </div>
                          <div>
                            <span className="vital-label">TA</span>
                            <span className="vital-value">{nota.signos_vitales.tension_arterial ?? '—'}</span>
                          </div>
                        </div>
                      )}

                      <div className="field-block">
                        <span className="overline">Diagnóstico (CIE-10)</span>
                        {nota.diagnosticos_cie10?.length ? (
                          <div className="cie10-diagnosis-list">
                            {nota.diagnosticos_cie10.map((diagnostico) => (
                              <div key={diagnostico.code}>
                                <strong className="mono">{diagnostico.code}</strong>
                                {' — '}{diagnostico.description}
                                {diagnostico.es_principal && <span className="badge badge-gold" style={{ marginLeft: '0.5rem' }}>Principal</span>}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p style={{ margin: 0 }}>{nota.contenido.diagnosticos?.[0] || nota.diagnostico_cie10 || 'N/A'}</p>
                        )}
                      </div>

                      <div className="field-block">
                        <span className="overline">Evolución clínica</span>
                        <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', lineHeight: 1.6 }}>
                          {nota.motivo_consulta && (
                            <><strong>Motivo de consulta:</strong><br />{nota.motivo_consulta}<br /><br /></>
                          )}
                          {nota.exploracion_fisica && (
                            <><strong>Exploración física:</strong><br />{nota.exploracion_fisica}<br /><br /></>
                          )}
                          {nota.plan_tratamiento && (
                            <><strong>Plan / Tratamiento:</strong><br />{nota.plan_tratamiento}<br /><br /></>
                          )}
                          {!nota.motivo_consulta && formatContenido(nota.contenido)}
                        </div>
                      </div>
                    </div>

                    {/* Gold signature seal */}
                    {nota.firmada && (
                      <div className="signed-banner">
                        <div className="signed-banner-title">
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                            <ShieldCheck size={15} />
                            Nota médica firmada · {new Date(nota.firmado_en!).toLocaleDateString()} · Cédula {nota.medico_cedula || 'N/A'}
                          </span>
                          <span style={{ display: 'inline-flex', gap: '0.5rem' }}>
                            <button
                              type="button"
                              className="btn btn-outline no-print"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', color: 'var(--color-gold)', borderColor: 'rgba(212,168,67,0.4)' }}
                              onClick={() => navigate(`/app/documentos/nota/${nota.id}/print`)}
                            >
                              <Printer size={12} /> Ver documento legal
                            </button>
                            <button
                              type="button"
                              className="btn btn-outline no-print"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => sendNoteVerificationWhatsApp(nota)}
                            >
                              <MessageCircle size={12} /> WhatsApp
                            </button>
                            <button
                              type="button"
                              className="btn btn-gold no-print"
                              style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                              onClick={() => { setActiveNotaForReceta(nota); setIsRecetaModalOpen(true); }}
                            >
                              <FileSignature size={12} /> Generar receta
                            </button>
                          </span>
                        </div>
                        <div className="signed-banner-meta">
                          <span><strong>Médico:</strong> {nota.medico_nombre}</span>
                          <span><strong>Especialidad:</strong> {nota.medico_especialidad}</span>
                          <span><strong>Firma:</strong> {new Date(nota.firmado_en!).toLocaleString()}</span>
                          <span className="mono"><strong>Hash:</strong> {nota.firma_hash_contenido?.substring(0, 16)}… ({nota.firma_algoritmo})</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Historia clínica ── */}
      {activeTab === 'historia' && (
        <div className="fade-in">
          <div className="glass-card" style={{ maxWidth: '860px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <ClipboardList size={18} color="var(--color-primary)" />
                <h3 style={{ margin: 0, fontSize: '1rem' }}>Antecedentes (AHF, APP, APNP)</h3>
              </div>
              <button className="btn btn-outline" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }} onClick={() => setIsAntecedentesModalOpen(true)}>
                <Edit3 size={13} /> Editar
              </button>
            </div>
            <div style={{
              padding: '1.1rem 1.25rem',
              backgroundColor: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.92rem',
              lineHeight: 1.7,
              whiteSpace: 'pre-wrap'
            }}>
              {expediente.antecedentes ? (
                <p style={{ margin: 0 }}>{expediente.antecedentes}</p>
              ) : (
                <p className="text-muted" style={{ margin: 0, fontStyle: 'italic' }}>Sin antecedentes registrados.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'archivos' && (
        <div className="fade-in">
          <ClinicalFiles expedienteId={expediente.id} />
          {id && <FotografiasPanel pacienteId={id} />}
        </div>
      )}

      {activeTab === 'consentimientos' && (
        <div className="fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ margin: 0 }}>Consentimientos informados</h2>
              <p className="text-muted" style={{ margin: '0.35rem 0 0' }}>Documenta consentimiento, firma y evidencia verificable para procedimientos.</p>
            </div>
            <button className="btn btn-primary" onClick={() => setIsConsentModalOpen(true)}>
              <Plus size={16} /> Nuevo consentimiento
            </button>
          </div>
          <div style={{ display: 'grid', gap: '1rem' }}>
            {consentimientos.length === 0 ? (
              <div className="empty-state glass-card">
                <div className="empty-state-title">Sin consentimientos informados</div>
                <p className="empty-state-hint">Crea un consentimiento para documentar el procedimiento y la aceptación del paciente.</p>
                <button type="button" className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => setIsConsentModalOpen(true)}>
                  <Plus size={16} /> Nuevo consentimiento
                </button>
              </div>
            ) : consentimientos.map((cons: any) => (
              <div key={cons.id} className="glass-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
                  <div>
                    <span className={cons.revocacion ? 'badge badge-draft' : cons.status === 'signed' ? 'badge badge-gold' : 'badge badge-draft'}>
                      {cons.revocacion ? 'Revocado' : cons.status === 'signed' ? 'Firmado' : 'Pendiente'}
                    </span>
                    <h3 style={{ margin: '0.75rem 0 0.35rem' }}>{cons.procedimiento}</h3>
                    <p className="text-muted" style={{ margin: 0 }}>{cons.template_key} · v{cons.version}</p>
                    {cons.hash_contenido && <p className="mono" style={{ fontSize: '0.78rem' }}>Hash: {cons.hash_contenido.substring(0, 18)}…</p>}
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {cons.status === 'signed' ? (
                      <>
                        <button className="btn btn-outline" onClick={() => navigate(`/app/documentos/consentimiento/${cons.id}/print`)}>
                          <Printer size={14} /> Abrir PDF final
                        </button>
                        {!cons.revocacion && (
                          <button className="btn btn-outline" onClick={async () => {
                            const motivo = window.prompt('Motivo de revocación (mínimo 10 caracteres). El original no se modificará:');
                            if (!motivo) return;
                            if (motivo.trim().length < 10) {
                              showToast('Escribe un motivo de al menos 10 caracteres.', 'error');
                              return;
                            }
                            try {
                              await revokeConsentWithReauthentication(cons.id, motivo.trim());
                              await client.invalidateQueries({ queryKey: ['consentimientos', expediente?.id] });
                              showToast('Revocación registrada. El original permanece inmutable.', 'success');
                            } catch (error) {
                              showToast(friendlyActionError(error, 'No se pudo registrar la revocación.'), 'error');
                            }
                          }}>
                            <AlertTriangle size={14} /> Revocar
                          </button>
                        )}
                      </>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        {signingCredentials.length > 0 && (
                          <select
                            className="form-input"
                            aria-label="Credencial para firma"
                            value={credentialByConsent[cons.id] || signingCredentials.find((item: any) => item.es_predeterminada)?.credencial_id || signingCredentials[0]?.credencial_id || ''}
                            onChange={(event) => setCredentialByConsent((current) => ({ ...current, [cons.id]: event.target.value }))}
                            style={{ width: 'auto', minWidth: '220px' }}
                          >
                            {signingCredentials.map((credential: any) => (
                              <option key={credential.credencial_id} value={credential.credencial_id}>
                                {credential.nombre} · {credential.especialidad} · {credential.cedula}
                              </option>
                            ))}
                          </select>
                        )}
                        <button className="btn btn-gold" onClick={async () => {
                          try {
                            const credentialId = credentialByConsent[cons.id]
                              || signingCredentials.find((item: any) => item.es_predeterminada)?.credencial_id
                              || signingCredentials[0]?.credencial_id;
                            await signConsentWithReauthentication(cons.id, credentialId);
                            await client.invalidateQueries({ queryKey: ['consentimientos', expediente?.id] });
                            showToast('Consentimiento finalizado: firma KMS y PDF único guardados.', 'success');
                          } catch (error) {
                            showToast(friendlyActionError(error, 'No se pudo finalizar el consentimiento.'), 'error');
                          }
                        }} disabled={!cons.firmado_paciente_en || signingCredentials.length === 0 || isDegraded}
                        title={isDegraded ? 'Firma bloqueada: el servidor no puede confirmar el guardado.' : undefined}>
                          <Lock size={14} /> Firmar y finalizar
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="glass-card" style={{ marginTop: '1rem' }}>
            <span className="overline">WhatsApp manual</span>
            <p className="text-muted">Envíos manuales registrados en la bitácora: {messageLogs.length}</p>
          </div>
        </div>
      )}

      {/* ── Side panel: encounter form (nueva consulta) ── */}
      <div className={isSidePanelOpen ? 'side-panel open no-print' : 'side-panel no-print'} aria-hidden={!isSidePanelOpen}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '1.15rem' }}>
            <FileSignature size={20} color="var(--color-primary)" />
            {editingNota ? 'Editar borrador' : 'Nueva consulta'}
          </h2>
          <button className="btn-icon" onClick={closeNoteEditor} aria-label="Cerrar panel">
            <X size={20} />
          </button>
        </div>

        <PatientIdentityBanner paciente={paciente} context="captura" />

        {!editingNota && seedDraft && (
          <div className="alert" role="note" style={{ marginBottom: '1rem', border: '1px solid var(--color-primary, #2563eb)', borderRadius: '8px', padding: '0.6rem 0.85rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
            <ClipboardList size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span style={{ fontSize: '0.85rem' }}>
              <strong>Datos heredados de una consulta previa</strong> (motivo y plan). Revísalos
              y actualízalos. Los signos vitales, la exploración y el diagnóstico
              <strong> no</strong> se copian: captúralos de nuevo.
            </span>
          </div>
        )}

        {!editingNota && (
          <p className="text-muted" style={{ fontSize: '0.78rem', marginBottom: '1rem' }}>
            Este borrador se guarda al presionar <strong>Guardar borrador</strong>. No se
            almacenan datos del paciente en este dispositivo.
          </p>
        )}

        <form key={formKey} id="nota-form" onSubmit={handleSubmitNota} onChange={handleFormChange}>
          <NoteTemplatePicker
            plantillas={notaPlantillas}
            onApply={applyNoteTemplate}
            onSaveCurrent={handleSaveNoteTemplate}
            canSave={noteHasContent()}
          />
          <div className="encounter-grid">
            {/* Left column: vital signs */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.75rem' }}>
                <span className="overline">Signos vitales</span>
                {editingNota && (
                  <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                    {isDegraded
                      ? 'Sin conexión — cambios sin guardar'
                      : autosave.status === 'saving'
                        ? 'Guardando…'
                        : autosave.status === 'saved'
                          ? 'Guardado en el servidor'
                          : autosave.status === 'error'
                            ? 'No se pudo guardar'
                            : 'Autoguardado activo'}
                  </span>
                )}
              </div>
              <div className="vitals-grid">
                <div className="form-group">
                  <label className="form-label" htmlFor="nota-fc">FC (lpm) <span className="required-mark">*</span></label>
                  <input id="nota-fc" type="number" name="fc" className="form-input" required defaultValue={editingNota?.signos_vitales?.frecuencia_cardiaca} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="nota-fr">FR (rpm) <span className="required-mark">*</span></label>
                  <input id="nota-fr" type="number" name="fr" className="form-input" required defaultValue={editingNota?.signos_vitales?.frecuencia_respiratoria} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="nota-temp">Temp (°C) <span className="required-mark">*</span></label>
                  <input id="nota-temp" type="number" step="0.1" name="temp" className="form-input" required defaultValue={editingNota?.signos_vitales?.temperatura} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="nota-ta">TA <span className="required-mark">*</span></label>
                  <input id="nota-ta" type="text" name="ta" className="form-input" placeholder="120/80" required pattern="\d{2,3}/\d{2,3}" title="Ej. 120/80" inputMode="numeric" onInput={(e) => e.currentTarget.value = e.currentTarget.value.replace(/[^\d/]/g, '')} defaultValue={editingNota?.signos_vitales?.tension_arterial} />
                </div>
              </div>
            </div>

            {/* Right column: clinical notes */}
            <div>
              <span className="overline" style={{ marginBottom: '0.75rem' }}>Contenido clínico</span>
              <div className="form-group" style={{ marginTop: '0.75rem' }}>
                <label className="form-label">Motivo de consulta y evolución <span className="required-mark">*</span></label>
                <textarea autoFocus name="motivo_consulta" className="form-input" rows={3} required minLength={5} placeholder="Describa el motivo y la evolución subjetiva…" defaultValue={editingNota?.motivo_consulta || editingNota?.contenido?.evolucion_y_actualizacion_cuadro || seedDraft?.motivo_consulta}></textarea>
              </div>

              <div className="form-group">
                <label className="form-label">Exploración física</label>
                <textarea name="exploracion_fisica" className="form-input" rows={3} placeholder="Describa los hallazgos objetivos…" defaultValue={editingNota?.exploracion_fisica}></textarea>
              </div>

              <div className="form-group">
                <label className="form-label">Diagnóstico clínico <span className="required-mark">*</span></label>
                <FavoritesPicker
                  favoritos={diagnosticoFavoritos}
                  label="Diagnósticos favoritos"
                  onInsert={(texto) => insertIntoNoteField('diagnostico', texto)}
                  onSaveCurrent={() => promptSaveNoteFavorito('diagnostico', 'diagnostico')}
                  canSave
                />
                <input type="text" name="diagnostico" className="form-input" required minLength={5} defaultValue={editingNota?.contenido?.diagnosticos?.[0]} />
              </div>

              <div className="form-group">
                <label className="form-label">Diagnósticos CIE-10</label>
                <Cie10DiagnosisSelector
                  value={diagnosticosCie10}
                  onChange={handleCie10Change}
                  readOnly={Boolean(editingNota)}
                />
                {editingNota && (
                  <p className="text-muted" style={{ marginTop: '0.45rem' }}>
                    Los diagnósticos estructurados se fijan al crear la nota. Para corregirlos,
                    crea un nuevo borrador antes de firmar.
                  </p>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">Plan / Tratamiento <span className="required-mark">*</span></label>
                <FavoritesPicker
                  favoritos={planFavoritos}
                  label="Planes favoritos"
                  onInsert={(texto) => insertIntoNoteField('plan_tratamiento', texto)}
                  onSaveCurrent={() => promptSaveNoteFavorito('plan', 'plan_tratamiento')}
                  canSave
                />
                <textarea name="plan_tratamiento" className="form-input" rows={3} required minLength={5} defaultValue={editingNota?.plan_tratamiento || editingNota?.contenido?.tratamiento || seedDraft?.plan_tratamiento}></textarea>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '1.75rem', display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="text-muted no-print" style={{ fontSize: '0.72rem', marginRight: 'auto' }}>
              Atajos: <kbd>⌘/Ctrl</kbd>+<kbd>S</kbd> guardar · <kbd>Esc</kbd> cerrar
            </span>
            <button type="button" className="btn btn-outline" onClick={closeNoteEditor}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={draftNotaMutation.isPending || updateNotaMutation.isPending}>
              {draftNotaMutation.isPending || updateNotaMutation.isPending ? 'Guardando nota…' : (editingNota ? 'Actualizar borrador' : 'Guardar borrador')}
            </button>
          </div>
        </form>
      </div>

      {/* Backdrop for side panel */}
      {isSidePanelOpen && (
        <div
          className="side-panel-backdrop no-print"
          onClick={() => setIsSidePanelOpen(false)}
        />
      )}

      {/* Sign Confirmation Modal */}
      <Modal
        isOpen={isSignModalOpen}
        onClose={() => setIsSignModalOpen(false)}
        title="Firmar nota médica"
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => setIsSignModalOpen(false)}>
              Revisar de nuevo
            </button>
            <button
              type="button"
              className="btn btn-gold"
              onClick={() => notaToSign && signNotaMutation.mutate(notaToSign.id)}
              disabled={signNotaMutation.isPending || isDegraded}
              title={isDegraded ? 'Firma bloqueada: el servidor no puede confirmar el guardado.' : undefined}
            >
              <Lock size={14} /> {signNotaMutation.isPending ? 'Firmando nota…' : 'Firmar nota'}
            </button>
          </>
        }
      >
        <PatientIdentityBanner paciente={paciente} context="firma" />
        <div className="alert alert-gold" style={{ marginBottom: '1.25rem' }}>
          <ShieldCheck size={18} style={{ flexShrink: 0, marginTop: '0.15rem' }} />
          <p style={{ margin: 0 }}>Al firmar esta nota médica, se genera evidencia verificable vinculada a tu identidad profesional y al contenido del documento.</p>
        </div>
        {isDegraded && (
          <div className="alert alert-danger" style={{ marginBottom: '1.25rem' }}>
            <Lock size={18} style={{ flexShrink: 0, marginTop: '0.15rem' }} />
            <p style={{ margin: 0 }}>
              La firma está bloqueada: el servidor no puede confirmar el guardado. Registra la
              atención en el <strong>formato de continuidad</strong> y firma al restablecerse.
            </p>
          </div>
        )}
        <p style={{ marginBottom: '0.75rem', fontWeight: 500, fontSize: '0.9rem' }}>
          De acuerdo con la NOM-004-SSA3-2012:
        </p>
        <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--color-muted-strong)' }}>
          <li style={{ marginBottom: '0.5rem' }}>La nota firmada queda protegida contra edición directa.</li>
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
        title="Editar antecedentes médicos"
      >
        <form onSubmit={handleUpdateAntecedentes}>
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">Incluya Antecedentes Heredofamiliares, Personales Patológicos, No Patológicos y Alergias (formato libre).</label>
            <textarea
              name="antecedentes"
              className="form-input"
              rows={8}
              defaultValue={expediente?.antecedentes || ''}
              placeholder="Ej. Padre finado por IAM. Diabetes mellitus tipo 2 diagnosticada hace 5 años. Alérgico a penicilina."
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" className="btn btn-outline" onClick={() => setIsAntecedentesModalOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={updateAntecedentesMutation.isPending}>
              {updateAntecedentesMutation.isPending ? 'Guardando…' : 'Guardar antecedentes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Receta Modal */}
      <Modal
        isOpen={isRecetaModalOpen}
        onClose={() => setIsRecetaModalOpen(false)}
        title="Generar receta"
        footer={
          <>
            <button type="button" className="btn btn-outline" onClick={() => setIsRecetaModalOpen(false)}>
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handlePrintReceta}
              disabled={!recetaText || createRecetaMutation.isPending}
            >
              <Printer size={15} />
              {createRecetaMutation.isPending ? 'Generando receta…' : 'Guardar e imprimir'}
            </button>
          </>
        }
      >
        <PatientIdentityBanner paciente={paciente} context="receta" />
        <FavoritesPicker
          favoritos={recetaFavoritos}
          label="Recetas favoritas"
          onInsert={(texto) => setRecetaText((prev) => (prev ? `${prev}\n${texto}` : texto))}
          onSaveCurrent={handleSaveRecetaFavorito}
          canSave={Boolean(recetaText.trim())}
        />
        <div className="form-group">
          <label className="form-label">Medicamentos e indicaciones <span className="required-mark">*</span></label>
          <textarea
            className="form-input"
            rows={8}
            value={recetaText}
            onChange={(e) => setRecetaText(e.target.value)}
            placeholder="Escriba aquí los medicamentos, dosis e indicaciones…"
          />
        </div>
      </Modal>

      <Modal
        isOpen={isConsentModalOpen}
        onClose={() => setIsConsentModalOpen(false)}
        title="Nuevo consentimiento informado"
      >
        <form onSubmit={(e) => {
          e.preventDefault();
          createConsentimientoMutation.mutate(new FormData(e.currentTarget));
        }}>
          <div className="form-group">
            <label className="form-label">Plantilla <span className="required-mark">*</span></label>
            <select
              className="form-input"
              value={selectedConsentTemplate}
              onChange={(e) => {
                setSelectedConsentTemplate(e.target.value);
                setWitnessSignatures([]);
              }}
            >
              {consentTemplates.map((tpl: any) => (
                <option key={tpl.key} value={tpl.key}>{tpl.nombre}</option>
              ))}
            </select>
            {(() => {
              const tpl = consentTemplates.find((t: any) => t.key === selectedConsentTemplate);
              return tpl ? (
                <div className="glass-card" style={{ marginTop: '0.75rem', padding: '0.85rem', fontSize: '0.83rem' }}>
                  <p style={{ margin: 0 }}><strong>Qué incluye:</strong> {tpl.descripcion}</p>
                  <p style={{ margin: '0.5rem 0 0', color: 'var(--color-muted-strong)' }}><strong>Riesgos base:</strong> {tpl.riesgos}</p>
                </div>
              ) : null;
            })()}
          </div>
          <div className="form-group">
            <label className="form-label">Procedimiento <span className="required-mark">*</span></label>
            <input name="procedimiento" className="form-input" required placeholder="Ej. Aplicación de toxina botulínica tercio superior" />
          </div>
          <div className="form-group">
            <label className="form-label">Riesgos principales</label>
            <textarea name="riesgos_principales" className="form-input" rows={3} placeholder="Opcional: si lo dejas vacío se usa el texto base de la plantilla." />
          </div>
          <div className="form-group">
            <label className="form-label">Quién firma <span className="required-mark">*</span></label>
            <select
              className="form-input"
              value={consentSignerType}
              onChange={(event) => setConsentSignerType(event.target.value as 'paciente' | 'representante' | 'tutor')}
            >
              <option value="paciente">Paciente</option>
              <option value="representante">Representante</option>
              <option value="tutor">Tutor</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Nombre completo del firmante <span className="required-mark">*</span></label>
            <input name="nombre_paciente" className="form-input" required defaultValue={paciente?.nombre_completo} />
          </div>
          {consentSignerType !== 'paciente' && (
            <div className="glass-card" style={{ padding: '0.9rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Relación con el paciente <span className="required-mark">*</span></label>
                <input name="relacion_paciente" className="form-input" required placeholder="Ej. madre, padre, representante legal" />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Motivo de representación <span className="required-mark">*</span></label>
                <textarea name="motivo_representacion" className="form-input" rows={2} required placeholder="Describe por qué firma en representación del paciente." />
              </div>
            </div>
          )}
          <label className="radio-card" style={{ margin: '1rem 0' }}>
            <input name="aceptado" type="checkbox" required style={{ marginTop: '0.2rem' }} />
            <span>El paciente declara que leyó el consentimiento, resolvió sus dudas y acepta firmarlo en este dispositivo.</span>
          </label>
          <SignaturePad
            label={`Firma de ${consentSignerType === 'paciente' ? 'paciente' : consentSignerType}`}
            required
            onChange={setConsentSignature}
          />
          {Array.from({ length: requiredWitnesses }, (_, index) => (
            <div key={`testigo-${index}`} className="glass-card" style={{ padding: '0.9rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Nombre del testigo {index + 1} <span className="required-mark">*</span></label>
                <input name={`testigo_${index + 1}_nombre`} className="form-input" required />
              </div>
              <SignaturePad
                label={`Firma del testigo ${index + 1}`}
                required
                onChange={(value) => setWitnessSignatures((current) => {
                  const next = [...current];
                  next[index] = value;
                  return next;
                })}
              />
            </div>
          ))}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
            <button type="button" className="btn btn-outline" onClick={() => setIsConsentModalOpen(false)}>Cancelar</button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={
                createConsentimientoMutation.isPending
                || !consentSignature
                || witnessSignatures.filter(Boolean).length !== requiredWitnesses
              }
            >
              {createConsentimientoMutation.isPending ? 'Guardando consentimiento…' : 'Crear y firmar paciente'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Hidden area only visible during printing for the Receta */}
      {isRecetaModalOpen && activeNotaForReceta && (
        <div id="print-receta-only" style={{ display: 'none' }} className="print-only">
          <div style={{ padding: '2rem', border: '1px solid #000', height: '100%' }}>
            <div style={{ textAlign: 'center', marginBottom: '2rem', borderBottom: '2px solid #000', paddingBottom: '1rem' }}>
              <h2>{activeNotaForReceta.medico_nombre}</h2>
              <p>Médico {activeNotaForReceta.medico_especialidad} | Cédula: {activeNotaForReceta.medico_cedula}</p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2rem' }}>
              <div>
                <p><strong>Paciente:</strong> {paciente?.nombre_completo}</p>
                <p><strong>Edad/Sexo:</strong> {paciente?.fecha_nacimiento} / {paciente?.sexo}</p>
                <p><strong>Alergias:</strong> {paciente?.alergias || 'Ninguna'}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p><strong>Fecha:</strong> {new Date().toLocaleDateString()}</p>
              </div>
            </div>

            <div style={{ minHeight: '400px' }}>
              <h3 style={{ borderBottom: '1px solid #ccc', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Rx</h3>
              <p style={{ whiteSpace: 'pre-wrap', fontSize: '1.1rem', lineHeight: '1.6' }}>{recetaText}</p>
            </div>

            <div style={{ marginTop: '4rem', textAlign: 'center' }}>
              <div style={{ borderTop: '1px solid #000', width: '300px', margin: '0 auto', paddingTop: '0.5rem' }}>
                Firma del Médico
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
