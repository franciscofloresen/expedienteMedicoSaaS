import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Printer } from 'lucide-react';
import { consentimientosApi, notasApi, recetasApi } from '../services/api';

function qrUrl(url?: string) {
  if (!url) return '';
  return `https://api.qrserver.com/v1/create-qr-code/?size=170x170&data=${encodeURIComponent(url)}`;
}

interface PrintDoc {
  tipo_documento?: string;
  medicamentos?: { descripcion?: string }[];
  contenido_renderizado?: string;
  motivo_consulta?: string;
  exploracion_fisica?: string;
  plan_tratamiento?: string;
}

function contentText(doc: PrintDoc) {
  if (doc.tipo_documento === 'receta') {
    return (doc.medicamentos || []).map((m) => m.descripcion || JSON.stringify(m)).join('\n\n');
  }
  if (doc.tipo_documento === 'consentimiento') return doc.contenido_renderizado;
  return [
    doc.motivo_consulta && `Motivo de consulta:\n${doc.motivo_consulta}`,
    doc.exploracion_fisica && `Exploración física:\n${doc.exploracion_fisica}`,
    doc.plan_tratamiento && `Plan / Tratamiento:\n${doc.plan_tratamiento}`,
  ].filter(Boolean).join('\n\n');
}

export default function PrintDocument() {
  const { kind, id } = useParams<{ kind: string; id: string }>();
  const { data: doc, isLoading, error } = useQuery({
    queryKey: ['print-doc', kind, id],
    queryFn: () => {
      if (kind === 'nota') return notasApi.legalPreview(id!);
      if (kind === 'receta') return recetasApi.print(id!);
      return consentimientosApi.print(id!);
    },
    enabled: !!kind && !!id,
  });

  if (isLoading) return <div style={{ padding: '3rem' }}>Preparando documento…</div>;
  if (error || !doc) return <div style={{ padding: '3rem' }}>No se pudo abrir el documento.</div>;

  const hash = doc.firma?.hash || doc.hash_contenido;
  const verificationUrl = doc.firma?.verification_url;

  return (
    <main style={{ background: '#f4f4f2', minHeight: '100vh', padding: '2rem' }}>
      <div className="no-print" style={{ maxWidth: '860px', margin: '0 auto 1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button className="btn btn-primary" onClick={() => window.print()}><Printer size={16} /> Imprimir / Guardar PDF</button>
      </div>
      <article style={{ maxWidth: '860px', minHeight: '1100px', margin: '0 auto', background: '#fff', color: '#111', padding: '3rem', boxShadow: '0 8px 30px rgba(0,0,0,0.12)' }}>
        <header style={{ borderBottom: '2px solid #111', paddingBottom: '1rem', marginBottom: '2rem' }}>
          <h1 style={{ margin: 0, fontSize: '1.7rem' }}>CloudMedRecord</h1>
          <p style={{ margin: '0.35rem 0 0' }}>Documento clínico firmado y verificable</p>
        </header>

        <section style={{ display: 'grid', gridTemplateColumns: '1fr 190px', gap: '2rem', marginBottom: '2rem' }}>
          <div>
            <p><strong>Folio:</strong> {doc.folio}</p>
            <p><strong>Tipo:</strong> {doc.tipo_documento}</p>
            <p><strong>Paciente:</strong> {doc.paciente?.nombre_completo}</p>
            <p><strong>Nacimiento / sexo:</strong> {doc.paciente?.fecha_nacimiento} / {doc.paciente?.sexo}</p>
            <p><strong>Expediente:</strong> {doc.expediente?.folio}</p>
            <p><strong>Médico:</strong> {doc.medico?.nombre || doc.medico_nombre}</p>
            <p><strong>Cédula:</strong> {doc.medico?.cedula || doc.medico_cedula}</p>
            <p><strong>Firmado:</strong> {doc.fechas?.firmado_en ? new Date(doc.fechas.firmado_en).toLocaleString() : doc.firmado_medico_en}</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            {verificationUrl && <img src={qrUrl(verificationUrl)} alt="QR de verificación" width={170} height={170} />}
            <p style={{ fontSize: '0.72rem', overflowWrap: 'anywhere' }}>{verificationUrl}</p>
          </div>
        </section>

        {doc.signos_vitales && (
          <section style={{ border: '1px solid #ccc', padding: '1rem', marginBottom: '2rem' }}>
            <strong>Signos vitales:</strong> FC {doc.signos_vitales.frecuencia_cardiaca || '-'} · FR {doc.signos_vitales.frecuencia_respiratoria || '-'} · Temp {doc.signos_vitales.temperatura || '-'} · TA {doc.signos_vitales.tension_arterial || '-'}
          </section>
        )}

        <section style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, minHeight: '360px' }}>
          {contentText(doc)}
        </section>

        <footer style={{ borderTop: '1px solid #999', marginTop: '2rem', paddingTop: '1rem', fontSize: '0.82rem' }}>
          <p><strong>Hash SHA-256:</strong> <span style={{ overflowWrap: 'anywhere' }}>{hash}</span></p>
          <p><strong>Algoritmo:</strong> {doc.firma?.algoritmo || 'ECDSA_SHA_256'}</p>
          <p>{doc.leyenda}</p>
        </footer>
      </article>
    </main>
  );
}
