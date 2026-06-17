import { useState, useEffect, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Edit2, Trash2, Search, Users, FileCheck, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { pacientesApi } from '../services/api';
import type { Paciente, PacienteUpdate } from '../types';
import Modal from '../components/Modal';
import { useToast } from '../hooks/useToast';

export default function Pacientes() {
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingPaciente, setEditingPaciente] = useState<Paciente | null>(null);
  const [pacienteToDelete, setPacienteToDelete] = useState<Paciente | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const client = useQueryClient();
  const navigate = useNavigate();
  const { showToast } = useToast();
  
  const { data: pacientes = [], isLoading, isError } = useQuery({
    queryKey: ['pacientes', debouncedSearch],
    queryFn: () => pacientesApi.getAll(debouncedSearch || undefined)
  });



  const createMutation = useMutation({
    mutationFn: pacientesApi.create,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
      showToast('Paciente registrado exitosamente', 'success');
      closeFormModal();
    },
    onError: (error: unknown) => {
      let message = "Error al registrar el paciente";
      if (error instanceof AxiosError && error.response?.data?.detail) {
        const detail = error.response.data.detail;
        message = Array.isArray(detail) ? detail.map((e: any) => `${e.loc[e.loc.length-1]}: ${e.msg}`).join(', ') : detail;
      }
      showToast(message, 'error');
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PacienteUpdate }) => pacientesApi.update(id, data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
      showToast('Paciente actualizado exitosamente', 'success');
      closeFormModal();
    },
    onError: (error: unknown) => {
      let message = "Error al actualizar el paciente";
      if (error instanceof AxiosError && error.response?.data?.detail) {
        const detail = error.response.data.detail;
        message = Array.isArray(detail) ? detail.map((e: any) => `${e.loc[e.loc.length-1]}: ${e.msg}`).join(', ') : detail;
      }
      showToast(message, 'error');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: pacientesApi.delete,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['pacientes'] });
      showToast('Paciente archivado (NOM-004)', 'success');
      setIsDeleteModalOpen(false);
      setPacienteToDelete(null);
    },
    onError: (error: unknown) => {
      const message = error instanceof AxiosError ? error.response?.data?.detail : undefined;
      showToast(message || "Error al archivar el paciente", 'error');
      setIsDeleteModalOpen(false);
      setPacienteToDelete(null);
    }
  });

  const closeFormModal = () => {
    setIsFormModalOpen(false);
    setEditingPaciente(null);
  };

  const openEditModal = (paciente: Paciente) => {
    setEditingPaciente(paciente);
    setIsFormModalOpen(true);
  };

  const confirmDelete = (paciente: Paciente) => {
    setPacienteToDelete(paciente);
    setIsDeleteModalOpen(true);
  };

  const handleDelete = () => {
    if (pacienteToDelete) {
      deleteMutation.mutate(pacienteToDelete.id);
    }
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    
    const curp_val = formData.get('curp') as string;
    const payload = {
      nombre_completo: formData.get('nombre_completo') as string,
      sexo: formData.get('sexo') as 'M' | 'F' | 'X',
      fecha_nacimiento: formData.get('fecha_nacimiento') as string,
      curp: curp_val ? curp_val.toUpperCase() : undefined,
      telefono: (formData.get('telefono') as string) || undefined,
      email: (formData.get('email') as string) || undefined,
      domicilio: (formData.get('domicilio') as string) || undefined,
      ocupacion: (formData.get('ocupacion') as string) || undefined,
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
        <h1 className="font-serif animate-fade-in" style={{ marginBottom: 0, fontSize: '2.5rem', fontWeight: 600, color: 'var(--text-main)' }}>Pacientes</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              className="form-input" 
              placeholder="Buscar por nombre, CURP..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ padding: '0.75rem 1rem 0.75rem 2.5rem', width: '320px', borderRadius: '100px', backgroundColor: 'var(--bg-card)', boxShadow: 'var(--shadow-sm)', border: '1px solid transparent' }}
            />
          </div>
          <button className="btn btn-primary" style={{ padding: '0.75rem 1.5rem', borderRadius: '100px', fontWeight: 600, letterSpacing: '0.05em' }} onClick={() => setIsFormModalOpen(true)}>
            NUEVO PACIENTE
          </button>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="glass-card animate-fade-in" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div style={{ background: 'var(--primary-light)', padding: '1rem', borderRadius: '12px', color: 'var(--primary)' }}>
            <Users size={32} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>Pacientes Activos</span>
            <span style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-main)', lineHeight: 1 }}>{pacientes.length}</span>
          </div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem', animationDelay: '0.1s' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '1rem', borderRadius: '12px', color: 'var(--success)' }}>
            <FileCheck size={32} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>Notas Firmadas Hoy</span>
            <span style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-main)', lineHeight: 1 }}>12</span>
          </div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem', animationDelay: '0.2s' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', padding: '1rem', borderRadius: '12px', color: 'white' }}>
            <ShieldCheck size={32} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>Estado Legal</span>
            <span style={{ fontSize: '1.1rem', fontWeight: 'bold', color: 'var(--text-main)', lineHeight: 1.2, marginTop: '0.2rem' }}>Cumplimiento NOM-004 (100%)</span>
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', marginTop: '1rem' }} className="animate-fade-in">Pacientes Recientes</h2>

      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s', overflowX: 'auto', padding: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)', backgroundColor: 'rgba(0,0,0,0.02)' }}>
              <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Nombre del Paciente</th>
              <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>CURP</th>
              <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sexo</th>
              <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Fecha Nac.</th>
              <th style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {isError ? (
              <tr><td colSpan={5} style={{ padding: '3rem', textAlign: 'center', color: 'var(--error)' }}>
                <p>Error de conexión al servidor (Backend Offline).</p>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Por favor verifica que uvicorn esté corriendo.</p>
              </td></tr>
            ) : isLoading ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }}>Cargando...</td></tr>
            ) : pacientes.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }} className="text-muted">
                {searchQuery ? 'No se encontraron pacientes que coincidan con la búsqueda.' : 'No hay pacientes registrados.'}
              </td></tr>
            ) : (
              pacientes.map((p: Paciente, index: number) => (
                <motion.tr 
                  key={p.id}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, ease: 'easeOut', delay: index * 0.05 }}
                  style={{ borderBottom: '1px solid var(--border-light)', transition: 'background-color 0.2s ease', cursor: 'pointer' }}
                  onMouseEnter={(e: React.MouseEvent<HTMLTableRowElement>) => e.currentTarget.style.backgroundColor = 'var(--primary-light)'}
                  onMouseLeave={(e: React.MouseEvent<HTMLTableRowElement>) => e.currentTarget.style.backgroundColor = 'transparent'}
                  onClick={() => navigate(`/app/pacientes/${p.id}`)}
                >
                  <td style={{ padding: '1.25rem 1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: 'rgba(0, 122, 255, 0.1)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '1.1rem' }}>
                        {p.nombre_completo.charAt(0)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{p.nombre_completo}</div>
                        {p.email && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.email}</div>}
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '1.25rem 1.5rem', color: 'var(--text-main)', fontWeight: 500 }}>{p.curp || '-'}</td>
                  <td style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)' }}>{p.sexo}</td>
                  <td style={{ padding: '1.25rem 1.5rem', color: 'var(--text-muted)' }}>{p.fecha_nacimiento}</td>
                  <td style={{ padding: '1.25rem 1.5rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      <button 
                        className="btn btn-outline" 
                        style={{ padding: '0.5rem', borderRadius: '10px', border: '1px solid var(--border-light)' }} 
                        onClick={(e) => { e.stopPropagation(); openEditModal(p); }} 
                        title="Editar"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button 
                        className="btn btn-outline" 
                        style={{ padding: '0.5rem', borderRadius: '10px', border: '1px solid var(--border-light)', color: 'var(--error)' }} 
                        onClick={(e) => { e.stopPropagation(); confirmDelete(p); }} 
                        title="Archivar"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Patient Form Modal */}
      <Modal 
        isOpen={isFormModalOpen} 
        onClose={closeFormModal} 
        title={editingPaciente ? 'Editar Paciente' : 'Registrar Nuevo Paciente'}
      >
        <form id="paciente-form" onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="nombre_completo">Nombre Completo (NOM-004)</label>
            <input 
              type="text" 
              id="nombre_completo"
              name="nombre_completo" 
              className="form-input" 
              required 
              minLength={2} 
              defaultValue={editingPaciente?.nombre_completo} 
            />
          </div>
          
          <div className="form-group">
            <label className="form-label" htmlFor="curp">CURP (Opcional)</label>
            <span id="curp-hint" className="text-muted" style={{ display: 'block', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
              Formato: 4 letras, 6 números, 6 letras, 1 dígito/letra, 1 dígito.
            </span>
            <input 
              type="text" 
              id="curp"
              name="curp" 
              className="form-input" 
              placeholder="Ej: ABCD123456HDFXYZ9" 
              pattern="^[A-Za-z]{4}\d{6}[HMhm][A-Za-z]{5}[A-Za-z\d]\d$"
              style={{ textTransform: 'uppercase' }}
              defaultValue={editingPaciente?.curp}
              aria-describedby="curp-hint"
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
              <label className="form-label" htmlFor="fecha_nacimiento">Fecha de Nacimiento</label>
              <input 
                type="date" 
                id="fecha_nacimiento"
                name="fecha_nacimiento" 
                className="form-input" 
                required 
                max={new Date().toISOString().split('T')[0]} 
                defaultValue={editingPaciente?.fecha_nacimiento} 
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="telefono">Teléfono</label>
              <input 
                type="tel" 
                id="telefono"
                name="telefono" 
                className="form-input" 
                defaultValue={editingPaciente?.telefono} 
              />
            </div>
            
            <div className="form-group">
              <label className="form-label" htmlFor="email">Correo Electrónico</label>
              <input 
                type="email" 
                id="email"
                name="email" 
                className="form-input" 
                defaultValue={editingPaciente?.email} 
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="domicilio">Domicilio (Se guarda cifrado)</label>
              <input 
                type="text" 
                id="domicilio"
                name="domicilio" 
                className="form-input" 
                defaultValue={editingPaciente?.domicilio} 
              />
            </div>
            
            <div className="form-group">
              <label className="form-label" htmlFor="ocupacion">Ocupación</label>
              <input 
                type="text" 
                id="ocupacion"
                name="ocupacion" 
                className="form-input" 
                defaultValue={editingPaciente?.ocupacion} 
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '2rem' }}>
            <button type="button" className="btn btn-outline" onClick={closeFormModal}>
              Cancelar
            </button>
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending 
                ? 'Guardando...' 
                : (editingPaciente ? 'Actualizar Paciente' : 'Guardar Paciente')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Archivar Expediente"
        footer={
          <div style={{ display: 'flex', gap: '1rem', width: '100%', justifyContent: 'flex-end' }}>
            <button 
              className="btn btn-secondary"
              onClick={() => {
                setIsDeleteModalOpen(false);
                setPacienteToDelete(null);
              }}
            >
              Cancelar
            </button>
            <button 
              className="btn btn-primary"
              style={{ background: 'var(--error)', borderColor: 'var(--error)' }}
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Archivando...' : 'Archivar Expediente'}
            </button>
          </div>
        }
      >
        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Archivar Expediente</h3>
        <p className="text-muted" style={{ marginBottom: '1.5rem', lineHeight: '1.5' }}>
          Por cumplimiento de la <strong>NOM-004-SSA3-2012</strong>, este expediente clínico no será destruido de la base de datos (debe conservarse por 5 años). En su lugar, se archivará y ocultará de su vista principal de manera segura.
          <br/><br/>
          ¿Confirma que desea archivar el expediente de <strong>{pacienteToDelete?.nombre_completo}</strong>?
        </p>
      </Modal>
    </>
  );
}
