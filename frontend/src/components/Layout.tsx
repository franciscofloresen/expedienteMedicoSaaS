import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, Users, FileText, Settings as SettingsIcon, LogOut, Menu, X, ShieldCheck } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';

export default function Layout() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);
  
  const handleNotImplemented = () => {
    showToast("Esta función está en construcción", "info");
    if (isMobileMenuOpen) setIsMobileMenuOpen(false);
  };

  return (
    <div className="app-container">
      {/* Mobile Header */}
      <div className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={24} color="var(--primary)" />
          <h2 className="page-title" style={{ fontSize: '1.25rem', margin: 0 }}>[Nombre en Construcción]</h2>
        </div>
        <button className="btn btn-icon" onClick={toggleMenu} aria-label="Menu">
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar Overlay for Mobile */}
      {isMobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setIsMobileMenuOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`glass-card sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header" style={{ marginBottom: '2.5rem' }}>
          <h2 className="page-title" style={{ fontSize: '1.5rem', marginBottom: 0 }}>[Nombre en Construcción]</h2>
          <span className="text-muted">Expediente Clínico</span>
        </div>
        
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <NavLink 
            to="/" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-main)' 
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <Users size={20} />
            Pacientes
          </NavLink>
          <NavLink 
            to="/expedientes" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-main)' 
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <FileText size={20} />
            Expedientes
          </NavLink>
          <NavLink 
            to="/notas" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-main)' 
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <Activity size={20} />
            Notas Médicas
          </NavLink>
          <NavLink 
            to="/auditoria" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-main)' 
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <ShieldCheck size={20} />
            Auditoría
          </NavLink>
        </nav>
        
        <div style={{ marginTop: 'auto' }}>
          {user && (
            <div className="user-info" style={{ marginBottom: '0.75rem' }}>
              <div className="user-info-name">{user.nombre_medico}</div>
              <div className="user-info-email">{user.email}</div>
            </div>
          )}
          <NavLink 
            to="/settings" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              width: '100%',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-main)' 
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <SettingsIcon size={20} />
            Configuración
          </NavLink>
          <button
            className="btn btn-outline"
            style={{ justifyContent: 'flex-start', border: 'none', width: '100%', color: 'var(--error)' }}
            onClick={logout}
          >
            <LogOut size={20} />
            Cerrar Sesión
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
