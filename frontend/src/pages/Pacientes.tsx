import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { pacientesApi } from '../services/api';

export default function Pacientes() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  
  const { data: pacientes = [], isLoading } = useQuery({
    queryKey: ['pacientes'],
    queryFn: pacientesApi.getAll
  });

  const createMutation = useMutation({
    mutationFn: pacientesApi.create,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
      setIsModalOpen(false);
    }
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createMutation.mutate({
      nombre_completo: formData.get('nombre_completo'),
      sexo: formData.get('sexo'),
      fecha_nacimiento: formData.get('fecha_nacimiento'),
    });
  };

  return (
    <>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 className="page-title animate-fade-in">Pacientes Recientes</h1>
        <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
          + Nuevo Paciente
        </button>
      </header>

      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Nombre del Paciente</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Sexo</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha Nac.</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} style={{ padding: '1rem', textAlign: 'center' }}>Cargando...</td></tr>
            ) : pacientes.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: '1rem', textAlign: 'center' }} className="text-muted">No hay pacientes registrados.</td></tr>
            ) : (
              pacientes.map((p: any) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '1rem', fontWeight: 500 }}>{p.nombre_completo}</td>
                  <td style={{ padding: '1rem' }} className="text-muted">{p.sexo}</td>
                  <td style={{ padding: '1rem' }}>{p.fecha_nacimiento}</td>
                  <td style={{ padding: '1rem' }}>
                    <button 
                      className="btn btn-outline" 
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }} 
                      onClick={() => navigate(`/pacientes/${p.id}`)}
                    >
                      Ver Expediente
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {isModalOpen && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
          backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
        }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '500px', backgroundColor: 'var(--bg-card)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Registrar Nuevo Paciente</h2>
              <button onClick={() => setIsModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={24} color="var(--text-muted)"/></button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Nombre Completo (NOM-004)</label>
                <input type="text" name="nombre_completo" className="form-input" required minLength={2} />
              </div>
              <div className="form-group">
                <label className="form-label">Sexo</label>
                <select name="sexo" className="form-input" required>
                  <option value="">Seleccione...</option>
                  <option value="M">Masculino</option>
                  <option value="F">Femenino</option>
                  <option value="X">Prefiero no decir / Otro</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Fecha de Nacimiento</label>
                <input type="date" name="fecha_nacimiento" className="form-input" required max={new Date().toISOString().split('T')[0]} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
                <button type="button" className="btn btn-outline" onClick={() => setIsModalOpen(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Guardando...' : 'Guardar Paciente'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
