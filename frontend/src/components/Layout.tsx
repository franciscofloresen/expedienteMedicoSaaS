import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, Users, FileText, Settings } from 'lucide-react';

export default function Layout() {
  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="glass-card" style={{ width: '260px', margin: '2rem 0 2rem 2rem', display: 'flex', flexDirection: 'column' }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h2 className="page-title" style={{ fontSize: '1.5rem', marginBottom: 0 }}>MedRecord</h2>
          <span className="text-muted">Expediente Clínico Electrónico</span>
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
          >
            <Users size={20} />
            Pacientes
          </NavLink>
          {/* Omitted other links for brevity as they are in construction */}
          <button className="btn btn-outline" style={{ justifyContent: 'flex-start', border: 'none' }} onClick={() => alert("En construcción")}>
            <FileText size={20} />
            Expedientes
          </button>
          <button className="btn btn-outline" style={{ justifyContent: 'flex-start', border: 'none' }} onClick={() => alert("En construcción")}>
            <Activity size={20} />
            Notas Médicas
          </button>
        </nav>
        
        <div style={{ marginTop: 'auto' }}>
          <button className="btn btn-outline" style={{ justifyContent: 'flex-start', border: 'none', width: '100%' }} onClick={() => alert("En construcción")}>
            <Settings size={20} />
            Configuración
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
