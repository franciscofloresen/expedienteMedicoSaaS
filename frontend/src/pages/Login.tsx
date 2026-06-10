/**
 * Login page — [Nombre en Construcción]
 *
 * Uses HTML5 validation attributes + :user-invalid CSS for
 * post-interaction validation feedback (modern best practice).
 */

import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AxiosError } from 'axios';
import { Activity, LogIn } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/app';

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    const formData = new FormData(e.currentTarget);

    try {
      await login({
        email: formData.get('email') as string,
        password: formData.get('password') as string,
      });
      navigate(from, { replace: true });
    } catch (err: unknown) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail || 'Error al iniciar sesión');
      } else {
        setError('Error de conexión. Verifique que el servidor esté activo.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card glass-card animate-fade-in">
        <div className="auth-header">
          <div className="auth-logo">
            <Activity size={32} color="var(--primary)" />
          </div>
          <h1 style={{ fontSize: '1.5rem', margin: 0, fontWeight: 700, color: 'var(--text-main)' }}>
            [Nombre en Construcción]
          </h1>
          <p className="text-muted">Expediente Clínico Electrónico</p>
        </div>

        {error && (
          <div className="auth-error animate-fade-in" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Correo electrónico</label>
            <input
              type="email"
              id="login-email"
              name="email"
              className="form-input"
              required
              autoComplete="email"
              placeholder="doctor@ejemplo.com"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Contraseña</label>
            <input
              type="password"
              id="login-password"
              name="password"
              className="form-input"
              required
              minLength={8}
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '1rem', padding: '0.75rem' }}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              'Ingresando...'
            ) : (
              <>
                <LogIn size={18} /> Iniciar Sesión
              </>
            )}
          </button>
        </form>

        <p className="auth-footer">
          ¿No tienes cuenta?{' '}
          <Link to="/register" className="auth-link">
            Regístrate aquí
          </Link>
        </p>
      </div>
    </div>
  );
}
