import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: '2rem',
          textAlign: 'center',
          backgroundColor: 'var(--bg-app)'
        }}>
          <div className="glass-card animate-fade-in" style={{ maxWidth: '500px', padding: '3rem' }}>
            <div style={{ color: 'var(--error)', marginBottom: '1.5rem', display: 'flex', justifyContent: 'center' }}>
              <AlertTriangle size={64} />
            </div>
            <h1 className="page-title" style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>
              Algo salió mal
            </h1>
            <p className="text-muted" style={{ marginBottom: '2rem' }}>
              Ocurrió un problema técnico cargando esta vista. Tus datos están seguros y guardados. Por favor intenta recargar la página.
            </p>
            <button className="btn btn-primary" onClick={this.handleReload} style={{ width: '100%', justifyContent: 'center' }}>
              <RefreshCw size={18} />
              Recargar Sistema
            </button>
            {import.meta.env.DEV && this.state.error && (
              <div style={{ marginTop: '2rem', textAlign: 'left', padding: '1rem', background: '#f8d7da', color: '#721c24', borderRadius: '8px', fontSize: '0.8rem', overflowX: 'auto' }}>
                <p style={{ margin: '0 0 0.5rem 0', fontWeight: 'bold' }}>Detalle Técnico (Solo Dev):</p>
                <pre style={{ margin: 0 }}>{this.state.error.toString()}</pre>
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
