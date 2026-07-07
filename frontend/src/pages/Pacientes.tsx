import { useState, useEffect, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { Edit2, Trash2, Search, Users, ShieldCheck, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { pacientesApi } from '../services/api';
import type { Paciente, PacienteUpdate } from '../types';
import Modal from '../components/Modal';
import { useToast } from '../hooks/useToast';

function initials(nombre: string): string {
  const parts = nombre.trim().split(/\s+/);
  return (parts[0]?.charAt(0) ?? '') + (parts[1]?.charAt(0) ?? '');
}

function edad(fechaNacimiento: string): number | null {
  const nacimiento = new Date(fechaNacimiento);
  if (isNaN(nacimiento.getTime())) return null;
  const hoy = new Date();
  let years = hoy.getFullYear() - nacimiento.getFullYear();
  const m = hoy.getMonth() - nacimiento.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < nacimiento.getDate())) years--;
  return years;
}

function EmptyPatients({ hasQuery, onCreate }: { hasQuery: boolean; onCreate: () => void }) {
  return (
    <div className="empty-state">
      <svg className="empty-illustration" width="120" height="90" viewBox="0 0 120 90" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="22" y="14" width="76" height="62" rx="8" stroke="var(--color-border)" strokeWidth="2" fill="var(--color-surface-2)" />
        <circle cx="60" cy="38" r="11" stroke="var(--color-primary)" strokeWidth="2" fill="var(--color-primary-tint)" />
        <path d="M40 66c2.5-9 10.5-14 20-14s17.5 5 20 14" stroke="var(--color-primary)" strokeWidth="2" strokeLinecap="round" fill="none" />
        <path d="M98 22h10M103 17v10" stroke="var(--color-gold)" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <div className="empty-state-title">
        {hasQuery ? 'Sin resultados' : 'No hay pacientes aún'}
      </div>
      <p className="empty-state-hint">
        {hasQuery
          ? 'Ningún paciente coincide con la búsqueda. Intenta con otro nombre o CURP.'
          : 'Registra a tu primer paciente para abrir su expediente clínico.'}
      </p>
      {!hasQuery && (
        <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={onCreate}>
          <UserPlus size={16} /> Registrar primer paciente
        </button>
      )}
    </div>
  );
}

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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    onError: (error: any) => {
      const message = error.response?.data?.detail || (error instanceof Error ? error.message : "Error al registrar el paciente");
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
      const message = error instanceof Error ? error.message : "Error al actualizar el paciente";
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
      const message = error instanceof Error ? error.message : "Error al archivar el paciente";
      showToast(message, 'error');
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
      contacto_emergencia: (formData.get('contacto_emergencia') as string) || undefined,
      telefono_emergencia: (formData.get('telefono_emergencia') as string) || undefined,
      tipo_sangre: (formData.get('tipo_sangre') as string) || undefined,
      alergias: (formData.get('alergias') as string) || undefined,
    };

    if (editingPaciente) {
      updateMutation.mutate({ id: editingPaciente.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  return (
    <>
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <h1 className="page-title">Pacientes</h1>
          <p className="page-subtitle">Directorio clínico de tu consulta</p>
        </div>
        <div className="page-header-actions" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div className="search-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="form-input"
              placeholder="Buscar por nombre o CURP…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: '300px' }}
            />
          </div>
          <button className="btn btn-primary" onClick={() => setIsFormModalOpen(true)}>
            <UserPlus size={16} /> Nuevo paciente
          </button>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-icon">
            <Users size={20} />
          </div>
          <div>
            <span className="overline">Pacientes activos</span>
            <div className="stat-value">{pacientes.length}</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon gold">
            <ShieldCheck size={20} />
          </div>
          <div>
            <span className="overline">Estado legal</span>
            <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Cumplimiento NOM-004</div>
          </div>
        </div>
      </div>

      <div className="table-card">
        {isError ? (
          <div className="empty-state">
            <div className="empty-state-title" style={{ color: 'var(--color-danger)' }}>Error de conexión al servidor</div>
            <p className="empty-state-hint">No fue posible cargar los pacientes. Verifica que el backend esté en línea.</p>
          </div>
        ) : isLoading ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Edad</th>
                <th>Sexo</th>
                <th>CURP</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {[0, 1, 2, 3].map(i => (
                <tr key={i}>
                  <td data-label="Paciente">
                    <div className="cell-person">
                      <div className="avatar skeleton" />
                      <span className="skeleton">Nombre del paciente</span>
                    </div>
                  </td>
                  <td data-label="Edad"><span className="skeleton">00</span></td>
                  <td data-label="Sexo"><span className="skeleton">M</span></td>
                  <td data-label="CURP"><span className="skeleton">XXXX000000XXXXXX00</span></td>
                  <td data-label="Acciones" />
                </tr>
              ))}
            </tbody>
          </table>
        ) : pacientes.length === 0 ? (
          <EmptyPatients hasQuery={!!searchQuery} onCreate={() => setIsFormModalOpen(true)} />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Edad</th>
                <th>Sexo</th>
                <th>CURP</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {pacientes.map((p: Paciente) => {
                const years = edad(p.fecha_nacimiento);
                return (
                  <tr
                    key={p.id}
                    className="row-link fade-in"
                    onClick={() => navigate(`/app/pacientes/${p.id}`)}
                  >
                    <td data-label="Paciente">
                      <div className="cell-person">
                        <div className="avatar">{initials(p.nombre_completo).toUpperCase()}</div>
                        <div>
                          <div className="cell-person-name">{p.nombre_completo}</div>
                          {p.email && <div className="cell-person-sub">{p.email}</div>}
                        </div>
                      </div>
                    </td>
                    <td data-label="Edad">{years !== null ? `${years} años` : '—'}</td>
                    <td data-label="Sexo" style={{ color: 'var(--color-muted)' }}>
                      {p.sexo === 'M' ? 'Masculino' : p.sexo === 'F' ? 'Femenino' : 'Otro'}
                    </td>
                    <td data-label="CURP" className="mono" style={{ color: 'var(--color-muted)' }}>{p.curp || '—'}</td>
                    <td data-label="Acciones">
                      <div className="cell-actions">
                        <button
                          className="btn-icon"
                          onClick={(e) => { e.stopPropagation(); openEditModal(p); }}
                          title="Editar"
                          aria-label={`Editar a ${p.nombre_completo}`}
                        >
                          <Edit2 size={15} />
                        </button>
                        <button
                          className="btn-icon"
                          style={{ color: 'var(--color-danger)' }}
                          onClick={(e) => { e.stopPropagation(); confirmDelete(p); }}
                          title="Archivar"
                          aria-label={`Archivar a ${p.nombre_completo}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Patient Form Modal */}
      <Modal
        isOpen={isFormModalOpen}
        onClose={closeFormModal}
        title={editingPaciente ? 'Editar paciente' : 'Registrar nuevo paciente'}
      >
        <form id="paciente-form" key={isFormModalOpen ? 'open' : 'closed'} onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="nombre_completo">Nombre completo (NOM-004)</label>
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
            <label className="form-label" htmlFor="curp">CURP (opcional)</label>
            <input
              type="text"
              id="curp"
              name="curp"
              className="form-input mono"
              placeholder="ABCD123456HDFXYZ9"
              pattern="^[A-Za-z]{4}\d{6}[HMhm][A-Za-z]{5}[A-Za-z\d]\d$"
              style={{ textTransform: 'uppercase' }}
              defaultValue={editingPaciente?.curp}
              aria-describedby="curp-hint"
            />
            <span id="curp-hint" className="text-muted" style={{ display: 'block', fontSize: '0.75rem', marginTop: '0.25rem' }}>
              Formato: 4 letras, 6 números, 6 letras, 1 dígito/letra, 1 dígito.
            </span>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Sexo</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.35rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input type="radio" name="sexo" value="M" required defaultChecked={editingPaciente?.sexo === 'M'} /> Masculino
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input type="radio" name="sexo" value="F" required defaultChecked={editingPaciente?.sexo === 'F'} /> Femenino
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                  <input type="radio" name="sexo" value="X" required defaultChecked={editingPaciente?.sexo === 'X'} /> Otro / ND
                </label>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="fecha_nacimiento">Fecha de nacimiento</label>
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

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="telefono">Teléfono</label>
              <input
                type="tel"
                id="telefono"
                name="telefono"
                className="form-input"
                pattern="\d{10}"
                title="Debe contener 10 dígitos"
                onInput={(e) => e.currentTarget.value = e.currentTarget.value.replace(/\D/g, '')}
                defaultValue={editingPaciente?.telefono}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="email">Correo electrónico</label>
              <input
                type="email"
                id="email"
                name="email"
                className="form-input"
                defaultValue={editingPaciente?.email}
              />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="domicilio">Domicilio (se guarda cifrado)</label>
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

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="contacto_emergencia">Contacto de emergencia</label>
              <input
                type="text"
                id="contacto_emergencia"
                name="contacto_emergencia"
                className="form-input"
                defaultValue={editingPaciente?.contacto_emergencia}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="telefono_emergencia">Teléfono de emergencia</label>
              <input
                type="tel"
                id="telefono_emergencia"
                name="telefono_emergencia"
                className="form-input"
                pattern="\d{10}"
                title="Debe contener 10 dígitos"
                onInput={(e) => e.currentTarget.value = e.currentTarget.value.replace(/\D/g, '')}
                defaultValue={editingPaciente?.telefono_emergencia}
              />
            </div>
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="tipo_sangre">Tipo de sangre</label>
              <input
                type="text"
                id="tipo_sangre"
                name="tipo_sangre"
                className="form-input"
                placeholder="Ej. O+"
                defaultValue={editingPaciente?.tipo_sangre}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="alergias">Alergias conocidas</label>
              <input
                type="text"
                id="alergias"
                name="alergias"
                className="form-input"
                placeholder="Ej. Penicilina, polen"
                defaultValue={editingPaciente?.alergias}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn-outline" onClick={closeFormModal}>
              Cancelar
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending
                ? 'Guardando…'
                : (editingPaciente ? 'Actualizar paciente' : 'Guardar paciente')}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Archivar expediente"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', width: '100%', justifyContent: 'flex-end' }}>
            <button
              className="btn btn-outline"
              onClick={() => {
                setIsDeleteModalOpen(false);
                setPacienteToDelete(null);
              }}
            >
              Cancelar
            </button>
            <button
              className="btn btn-danger"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Archivando…' : 'Archivar expediente'}
            </button>
          </div>
        }
      >
        <p className="text-muted" style={{ lineHeight: 1.6 }}>
          Por cumplimiento de la <strong style={{ color: 'var(--color-text)' }}>NOM-004-SSA3-2012</strong>, este expediente clínico no será destruido de la base de datos (debe conservarse por 5 años). En su lugar, se archivará y ocultará de su vista principal de manera segura.
          <br /><br />
          ¿Confirma que desea archivar el expediente de <strong style={{ color: 'var(--color-text)' }}>{pacienteToDelete?.nombre_completo}</strong>?
        </p>
      </Modal>
    </>
  );
}
