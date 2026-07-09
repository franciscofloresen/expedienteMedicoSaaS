import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth, useUser } from '@clerk/react';

export default function ProtectedRoute() {
  const { isLoaded, userId } = useAuth();
  const { user } = useUser();
  const location = useLocation();

  if (!isLoaded || (userId && !user)) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        color: 'var(--text-muted)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" />
          <p style={{ marginTop: '1rem' }}>Verificando sesión…</p>
        </div>
      </div>
    );
  }

  if (!userId) {
    // Redirect to login
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  // If authenticated but missing tenant_id, force onboarding
  const hasTenant = user?.publicMetadata?.tenant_id;
  
  if (!hasTenant && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  // If they have a tenant but try to access onboarding, send them to the app
  if (hasTenant && location.pathname === '/onboarding') {
    return <Navigate to="/app" replace />;
  }

  return <Outlet />;
}
