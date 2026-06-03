import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { X, Edit2, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { pacientesApi } from '../services/api';

export default function Pacientes() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPaciente, setEditingPaciente] = useState<any>(null);
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
      closeModal();
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => pacientesApi.update(id, data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
      closeModal();
    }
  });

  const deleteMutation = useMutation({
    mutationFn: pacientesApi.delete,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || "Error al eliminar el paciente");
    }
  });

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingPaciente(null);
  };

  const openEditModal = (paciente: any) => {
    setEditingPaciente(paciente);
    setIsModalOpen(true);
  };

  const handleDelete = (id: string) => {
    if (window.confirm("¿Estás seguro de eliminar a este paciente? Si ya tiene un expediente clínico, no se podrá eliminar.")) {
      deleteMutation.mutate(id);
    }
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    
    const curp_val = formData.get('curp') as string;
    const payload = {
      nombre_completo: formData.get('nombre_completo'),
      sexo: formData.get('sexo'),
      fecha_nacimiento: formData.get('fecha_nacimiento'),
      curp: curp_val ? curp_val.toUpperCase() : undefined,
    };
    
    if (editingPaciente) {
      updateMutation.mutate({ id: editingPaciente.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
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
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>CURP</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Sexo</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha Nac.</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }}>Cargando...</td></tr>
            ) : pacientes.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }} className="text-muted">No hay pacientes registrados.</td></tr>
            ) : (
              pacientes.map((p: any) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '1rem', fontWeight: 500 }}>{p.nombre_completo}</td>
                  <td style={{ padding: '1rem', fontFamily: 'monospace', fontSize: '0.9rem' }} className="text-muted">{p.curp || 'N/A'}</td>
                  <td style={{ padding: '1rem' }} className="text-muted">{p.sexo}</td>
                  <td style={{ padding: '1rem' }}>{p.fecha_nacimiento}</td>
                  <td style={{ padding: '1rem', display: 'flex', gap: '0.5rem' }}>
                    <button 
                      className="btn btn-outline" 
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }} 
                      onClick={() => navigate(`/pacientes/${p.id}`)}
                    >
                      Expediente
                    </button>
                    <button 
                      className="btn btn-outline" 
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', borderColor: 'transparent', color: 'var(--text-muted)' }} 
                      onClick={() => openEditModal(p)}
                      title="Editar Paciente"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button 
                      className="btn btn-outline" 
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', borderColor: 'transparent', color: 'var(--error)' }} 
                      onClick={() => handleDelete(p.id)}
                      title="Eliminar Paciente"
                    >
                      <Trash2 size={16} />
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
              <h2 style={{ fontSize: '1.25rem', margin: 0 }}>{editingPaciente ? 'Editar Paciente' : 'Registrar Nuevo Paciente'}</h2>
              <button onClick={closeModal} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={24} color="var(--text-muted)"/></button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Nombre Completo (NOM-004)</label>
                <input type="text" name="nombre_completo" className="form-input" required minLength={2} defaultValue={editingPaciente?.nombre_completo} />
              </div>
              <div className="form-group">
                <label className="form-label">CURP (Opcional)</label>
                <input 
                  type="text" 
                  name="curp" 
                  className="form-input" 
                  placeholder="18 caracteres" 
                  minLength={18} 
                  maxLength={18} 
                  style={{ textTransform: 'uppercase' }}
                  defaultValue={editingPaciente?.curp}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Sexo</label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input type="radio" name="sexo" value="M" required defaultChecked={editingPaciente?.sexo === 'M'} /> Masculino
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input type="radio" name="sexo" value="F" required defaultChecked={editingPaciente?.sexo === 'F'} /> Femenino
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                      <input type="radio" name="sexo" value="X" required defaultChecked={editingPaciente?.sexo === 'X'} /> Otro / ND
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Fecha de Nacimiento</label>
                  <input type="date" name="fecha_nacimiento" className="form-input" required max={new Date().toISOString().split('T')[0]} defaultValue={editingPaciente?.fecha_nacimiento} />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
                <button type="button" className="btn btn-outline" onClick={closeModal}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                  {editingPaciente ? 'Actualizar Paciente' : 'Guardar Paciente'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
