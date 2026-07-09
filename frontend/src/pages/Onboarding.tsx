/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { authApi } from '../services/api';
import { Activity } from 'lucide-react';
import { useAuth } from '@clerk/react';
import { useToast } from '../hooks/useToast';

export default function Onboarding() {
  const [nombre, setNombre] = useState('');
  const [cedula, setCedula] = useState('');
  const [especialidad, setEspecialidad] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { getToken } = useAuth();
  const { showToast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // First ensure we have a valid Clerk token before calling backend
      await getToken();
      
      const res = await authApi.onboarding({
        nombre_medico: nombre,
        cedula,
        especialidad: especialidad || 'General'
      });
      
      if (res.status === 'success' || res.status === 'already_onboarded') {
        showToast('Perfil configurado correctamente', 'success');
        // Force Clerk SDK to fetch a NEW token that includes the newly assigned tenant_id
        // @ts-expect-error - Clerk is injected into window by the SDK
        await window.Clerk?.session?.getToken({ skipCache: true });
        window.location.href = '/app';
      }
    } catch (err: any) {
      console.error(err);
      showToast(err.response?.data?.detail || 'No pudimos guardar tu perfil profesional. Intenta de nuevo.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-main)',
      padding: '2rem'
    }}>
      <div 
        className="glass-card"
        style={{
          width: '100%',
          maxWidth: '500px',
          padding: '3rem 2rem',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-glass)',
          border: '1px solid var(--color-border)',
          background: 'var(--color-surface)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{
            background: 'var(--color-primary-tint)',
            border: '1px solid rgba(0, 194, 184, 0.35)',
            width: '64px', height: '64px',
            borderRadius: '18px',
            color: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.5rem'
          }}>
            <Activity size={32} />
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.5rem', letterSpacing: '-0.03em' }}>
            Completar perfil médico
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem' }}>
            Configura los datos que aparecerán en notas, recetas y consentimientos.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }} htmlFor="onboarding-nombre">Nombre completo <span className="required-mark">*</span></label>
            <input
              id="onboarding-nombre"
              type="text"
              className="form-input"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej. Dr. Juan Pérez"
              required
              minLength={2}
              autoComplete="name"
              style={{ padding: '1rem', fontSize: '1rem' }}
            />
          </div>
          
          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }} htmlFor="onboarding-cedula">Cédula profesional <span className="required-mark">*</span></label>
            <input
              id="onboarding-cedula"
              type="text"
              className="form-input"
              value={cedula}
              onChange={(e) => setCedula(e.target.value)}
              placeholder="Ej. 1234567"
              required
              minLength={5}
              style={{ padding: '1rem', fontSize: '1rem' }}
            />
            <p className="form-help">
              Requerido por la NOM-004 para la firma de notas médicas.
            </p>
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }} htmlFor="onboarding-especialidad">Especialidad</label>
            <input
              id="onboarding-especialidad"
              type="text"
              className="form-input"
              value={especialidad}
              onChange={(e) => setEspecialidad(e.target.value)}
              placeholder="Ej. Medicina General, Cardiología"
              autoComplete="organization-title"
              style={{ padding: '1rem', fontSize: '1rem' }}
            />
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={loading}
            style={{
              padding: '1rem',
              fontSize: '1.1rem',
              fontWeight: 600,
              marginTop: '1rem',
              borderRadius: '12px'
            }}
          >
            {loading ? 'Guardando perfil…' : 'Comenzar a usar CloudMedRecord'}
          </button>
        </form>
      </div>
    </div>
  );
}
