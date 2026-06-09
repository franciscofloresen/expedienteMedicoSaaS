/**
 * Register page — [Nombre en Construcción]
 *
 * Collects doctor's professional information to create a tenant.
 * Uses HTML5 validation + autocomplete for best UX.
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { Activity, UserPlus } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    const formData = new FormData(e.currentTarget);
    const password = formData.get('password') as string;
    const confirmPassword = formData.get('confirm_password') as string;

    if (password !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      setIsSubmitting(false);
      return;
    }

    try {
      await register({
        nombre_medico: formData.get('nombre_medico') as string,
        cedula: formData.get('cedula') as string,
        especialidad: (formData.get('especialidad') as string) || undefined,
        email: formData.get('email') as string,
        password,
      });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail || 'Error al registrar la cuenta');
      } else {
        setError('Error de conexión. Verifique que el servidor esté activo.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card glass-card animate-fade-in" style={{ maxWidth: '480px' }}>
        <div className="auth-header">
          <div className="auth-logo">
            <Activity size={32} color="var(--primary)" />
          </div>
          <h1 className="page-title" style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>
            Crear Cuenta
          </h1>
          <p className="text-muted">Expediente Clínico Electrónico — NOM-004</p>
        </div>

        {error && (
          <div className="auth-error animate-fade-in" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="reg-nombre">Nombre completo del médico</label>
            <input
              type="text"
              id="reg-nombre"
              name="nombre_medico"
              className="form-input"
              required
              minLength={3}
              autoComplete="name"
              placeholder="Dr. Juan Pérez López"
              autoFocus
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-cedula">Cédula profesional</label>
              <input
                type="text"
                id="reg-cedula"
                name="cedula"
                className="form-input"
                required
                minLength={5}
                maxLength={20}
                placeholder="12345678"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-especialidad">Especialidad</label>
              <input
                type="text"
                id="reg-especialidad"
                name="especialidad"
                className="form-input"
                placeholder="Medicina General"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-email">Correo electrónico</label>
            <input
              type="email"
              id="reg-email"
              name="email"
              className="form-input"
              required
              autoComplete="email"
              placeholder="doctor@ejemplo.com"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-password">Contraseña</label>
              <input
                type="password"
                id="reg-password"
                name="password"
                className="form-input"
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="Mín. 8 caracteres"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="reg-confirm">Confirmar contraseña</label>
              <input
                type="password"
                id="reg-confirm"
                name="confirm_password"
                className="form-input"
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="Repetir contraseña"
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '1rem', padding: '0.75rem' }}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              'Creando cuenta...'
            ) : (
              <>
                <UserPlus size={18} /> Crear Cuenta
              </>
            )}
          </button>
        </form>

        <p className="auth-footer">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="auth-link">
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
