import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, Users, FileText, Settings as SettingsIcon, Menu, X, ShieldCheck, Calendar as CalendarIcon } from 'lucide-react';
import { UserButton } from '@clerk/react';
import { motion, AnimatePresence } from 'framer-motion';
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
            style={({ isActive }) => ({ 
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.75rem 1rem', borderRadius: '12px',
              textDecoration: 'none',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            {({ isActive }) => (
              <>
                <CalendarIcon size={20} style={{ opacity: isActive ? 1 : 0.8 }} />
                Agenda
              </>
            )}
          </NavLink>
          <NavLink 
            to="/app" 
            end
            style={({ isActive }) => ({ 
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.75rem 1rem', borderRadius: '12px',
              textDecoration: 'none',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            {({ isActive }) => (
              <>
                <Users size={20} style={{ opacity: isActive ? 1 : 0.8 }} />
                Pacientes
              </>
            )}
          </NavLink>
          <NavLink 
            to="/app/expedientes" 
            style={({ isActive }) => ({ 
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.75rem 1rem', borderRadius: '12px',
              textDecoration: 'none',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            {({ isActive }) => (
              <>
                <FileText size={20} style={{ opacity: isActive ? 1 : 0.8 }} />
                Expedientes
              </>
            )}
          </NavLink>
          <NavLink 
            to="/app/notas" 
            style={({ isActive }) => ({ 
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.75rem 1rem', borderRadius: '12px',
              textDecoration: 'none',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            {({ isActive }) => (
              <>
                <Activity size={20} style={{ opacity: isActive ? 1 : 0.8 }} />
                Notas Médicas
              </>
            )}
          </NavLink>
          <NavLink 
            to="/app/auditoria" 
            style={({ isActive }) => ({ 
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.75rem 1rem', borderRadius: '12px',
              textDecoration: 'none',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            {({ isActive }) => (
              <>
                <ShieldCheck size={20} style={{ opacity: isActive ? 1 : 0.8 }} />
                Auditoría
              </>
            )}
          </NavLink>
        </nav>
        
        <div style={{ marginTop: 'auto', paddingTop: '1.5rem', borderTop: '1px solid var(--border-light)' }}>
          <div style={{ marginBottom: '1rem', padding: '0.5rem', border: 'none', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <UserButton showName />
          </div>
          <NavLink 
            to="/app/settings" 
            className={({ isActive }) => `btn btn-outline ${isActive ? 'active-link' : ''}`} 
            style={({ isActive }) => ({ 
              justifyContent: 'flex-start', 
              border: 'none', 
              width: '100%',
              padding: '0.75rem 1rem',
              borderRadius: '12px',
              backgroundColor: isActive ? 'var(--primary-light)' : 'transparent', 
              color: isActive ? 'var(--primary)' : 'var(--text-muted)',
              fontWeight: 600,
              fontSize: '0.8rem',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              transition: 'all 0.2s ease'
            })}
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <SettingsIcon size={20} style={{ opacity: 0.8 }} />
            CONFIGURACIÓN
          </NavLink>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            style={{ width: '100%', height: '100%' }}
          >
            <ConnectionStatus />
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
