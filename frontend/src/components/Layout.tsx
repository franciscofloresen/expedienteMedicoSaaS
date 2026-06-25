import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, Users, FileText, Settings as SettingsIcon, Menu, X, Calendar as CalendarIcon } from 'lucide-react';
import { UserButton } from '@clerk/react';
import { ConnectionStatus } from './ConnectionStatus';


export default function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const toggleMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);

  return (
    <div className="app-container">
      <div className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', padding: '0.4rem', borderRadius: '8px', color: 'white', display: 'flex' }}>
            <Activity size={20} />
          </div>
          <span className="font-serif" style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>CloudMedRecord</span>
        </div>
        <button className="btn btn-icon" style={{ background: 'transparent', border: 'none', color: 'var(--text-main)' }} onClick={toggleMenu} aria-label="Menu">
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar Overlay for Mobile */}
      {isMobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setIsMobileMenuOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`glass-card sidebar ${isMobileMenuOpen ? 'open' : ''}`} style={{ padding: '1.5rem 1rem', border: 'none', boxShadow: '0 4px 24px rgba(0,0,0,0.04)', borderRadius: '24px' }}>
        <div className="sidebar-header" style={{ marginBottom: '2.5rem', padding: '0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--primary), var(--accent))', padding: '0.5rem', borderRadius: '10px', color: 'white', display: 'flex', boxShadow: '0 4px 12px rgba(0,122,255,0.3)' }}>
            <Activity size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.4rem', marginBottom: 0, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-main)' }}>CloudMedRecord</h2>
            <span className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 500, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Clínico</span>
          </div>
        </div>
        
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <NavLink 
            to="/app/agenda" 
            className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <CalendarIcon size={20} className="nav-icon" />
            Agenda
          </NavLink>
          <NavLink 
            to="/app" 
            end
            className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <Users size={20} className="nav-icon" />
            Pacientes
          </NavLink>
          <NavLink 
            to="/app/expedientes" 
            className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <FileText size={20} className="nav-icon" />
            Expedientes
          </NavLink>
          <NavLink 
            to="/app/notas" 
            className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <Activity size={20} className="nav-icon" />
            Notas Médicas
          </NavLink>

        </nav>
        
        <div style={{ marginTop: 'auto', paddingTop: '1.5rem', borderTop: '1px solid var(--border-light)' }}>
          <div style={{ marginBottom: '1rem', padding: '0.5rem', border: 'none', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <UserButton showName />
          </div>
          <NavLink 
            to="/app/settings" 
            className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <SettingsIcon size={20} className="nav-icon" />
            CONFIGURACIÓN
          </NavLink>
        </div>
      </aside>

      <main className="main-content">
        <div key={location.pathname} className="fade-in" style={{ width: '100%', height: '100%' }}>
          <ConnectionStatus />

          <Outlet />
        </div>
      </main>
    </div>
  );
}
