import { useState, useEffect, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Edit2, Trash2, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { pacientesApi, auditApi } from '../services/api';
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

  const { data: auditLogs = [], isLoading: isLoadingAudit } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: auditApi.getRecent
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
      showToast('Paciente eliminado correctamente', 'success');
      setIsDeleteModalOpen(false);
      setPacienteToDelete(null);
    },
    onError: (error: unknown) => {
      const message = error instanceof AxiosError ? error.response?.data?.detail : undefined;
      showToast(message || "Error al eliminar el paciente", 'error');
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
        <h1 className="page-title animate-fade-in" style={{ marginBottom: 0 }}>Pacientes</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input 
              type="text" 
              className="form-input" 
              placeholder="Buscar por nombre, CURP..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '2.5rem', width: '300px' }}
            />
          </div>
          <button className="btn btn-primary" onClick={() => setIsFormModalOpen(true)}>Nuevo Paciente</button>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="glass-card animate-fade-in" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>Total de Pacientes</span>
          <span style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--primary)' }}>{pacientes.length}</span>
        </div>
        <div className="glass-card animate-fade-in" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', animationDelay: '0.1s' }}>
          <span className="text-muted" style={{ textTransform: 'uppercase', fontSize: '0.85rem', fontWeight: 600 }}>Eventos de Auditoría (Recientes)</span>
          <span style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--success)' }}>{auditLogs.length}</span>
          <span className="text-muted" style={{ fontSize: '0.8rem' }}>Eventos recientes de bitácora</span>
        </div>
      </div>

      <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', marginTop: '1rem' }} className="animate-fade-in">Pacientes Recientes</h2>

      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.1s', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px' }}>
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
              pacientes.map((p: Paciente) => (
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
                      onClick={() => confirmDelete(p)}
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

      {/* Bitácora Reciente */}
      <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem', marginTop: '2rem' }} className="animate-fade-in">Bitácora Reciente (Auditoría)</h2>
      
      <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s', overflowX: 'auto', marginBottom: '2rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Fecha/Hora</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Método</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Ruta</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>Status</th>
              <th style={{ padding: '1rem', color: 'var(--text-muted)', fontWeight: 500 }}>IP</th>
            </tr>
          </thead>
          <tbody>
            {isLoadingAudit ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }}>Cargando bitácora...</td></tr>
            ) : auditLogs.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: '1rem', textAlign: 'center' }} className="text-muted">No hay eventos recientes.</td></tr>
            ) : (
              auditLogs.slice(0, 10).map((log: any) => (
                <tr key={log.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace' }}>{new Date(log.timestamp).toLocaleString()}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span style={{ 
                      padding: '0.2rem 0.5rem', 
                      borderRadius: '4px', 
                      backgroundColor: log.metodo === 'DELETE' ? 'rgba(255,0,0,0.1)' : 'rgba(0,150,255,0.1)',
                      color: log.metodo === 'DELETE' ? 'var(--error)' : 'var(--primary)',
                      fontWeight: 600,
                      fontSize: '0.8rem'
                    }}>{log.metodo}</span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace' }}>{log.ruta}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span style={{ color: log.status >= 400 ? 'var(--error)' : 'var(--success)' }}>
                      {log.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{log.ip_origen}</td>
                </tr>
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
        title="Confirmar eliminación"
        footer={
          <>
            <button className="btn btn-outline" onClick={() => setIsDeleteModalOpen(false)}>
              Cancelar
            </button>
            <button 
              className="btn btn-primary" 
              style={{ backgroundColor: 'var(--error)' }} 
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Eliminando...' : 'Eliminar paciente'}
            </button>
          </>
        }
      >
        <p>¿Estás seguro de que deseas eliminar al paciente <strong>{pacienteToDelete?.nombre_completo}</strong>?</p>
        <p className="text-muted" style={{ marginTop: '1rem', fontSize: '0.9rem' }}>
          De acuerdo con la NOM-004, los expedientes clínicos deben conservarse por un mínimo de 5 años. 
          Si el paciente tiene registros clínicos, esta acción solo lo ocultará de tu lista principal.
        </p>
      </Modal>
    </>
  );
}
