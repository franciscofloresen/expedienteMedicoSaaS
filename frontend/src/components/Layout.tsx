import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Activity, Users, FileText, Settings as SettingsIcon, Calendar as CalendarIcon } from 'lucide-react';
import { UserButton } from '@clerk/react';
import { ConnectionStatus } from './ConnectionStatus';

const NAV_ITEMS = [
  { to: '/app/agenda', label: 'Agenda', icon: CalendarIcon, end: false },
  { to: '/app', label: 'Pacientes', icon: Users, end: true },
  { to: '/app/expedientes', label: 'Expedientes', icon: FileText, end: false },
  { to: '/app/notas', label: 'Notas', icon: Activity, end: false },
];

function breadcrumbFor(pathname: string): string[] {
  if (pathname.startsWith('/app/pacientes/')) return ['Pacientes', 'Expediente clínico'];
  if (pathname.startsWith('/app/agenda')) return ['Agenda'];
  if (pathname.startsWith('/app/expedientes')) return ['Expedientes'];
  if (pathname.startsWith('/app/notas')) return ['Notas médicas'];
  if (pathname.startsWith('/app/settings')) return ['Configuración'];
  return ['Pacientes'];
}

export default function Layout() {
  const location = useLocation();
  const crumbs = breadcrumbFor(location.pathname);

  return (
    <div className="app-container">
      {/* Sidebar — desktop */}
      <aside className="sidebar no-print">
        <div className="sidebar-brand">
          <img src="/faviconC.png" alt="CloudMedRecord" />
          <div>
            <div className="sidebar-brand-name">CloudMedRecord</div>
            <div className="sidebar-brand-tag">Clínico</div>
          </div>
        </div>

        <nav className="sidebar-section" aria-label="Navegación principal">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
            >
              <Icon size={17} className="nav-icon" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <NavLink
            to="/app/settings"
            className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
          >
            <SettingsIcon size={17} className="nav-icon" />
            Configuración
          </NavLink>
        </div>
      </aside>

      <main className="main-content">
        {/* Topbar — desktop */}
        <div className="topbar no-print">
          <div className="breadcrumb">
            {crumbs.map((crumb, i) => {
              const isLast = i === crumbs.length - 1;
              return (
                <span key={crumb} className={isLast ? 'crumb-current' : undefined} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  {crumb}
                  {!isLast && <span className="crumb-sep">/</span>}
                </span>
              );
            })}
          </div>
          <div className="topbar-actions">
            <UserButton showName />
          </div>
        </div>

        {/* Mobile header */}
        <div className="mobile-header no-print">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <img src="/faviconC.png" alt="CloudMedRecord" style={{ height: '26px', width: 'auto', borderRadius: '6px' }} />
            <span className="font-serif" style={{ fontSize: '1.1rem', color: 'var(--color-text)' }}>CloudMedRecord</span>
          </div>
          <UserButton />
        </div>

        <div key={location.pathname} className="page-body fade-in">
          <ConnectionStatus />
          <Outlet />
        </div>

        {/* Bottom navigation — mobile */}
        <nav className="bottom-nav no-print" aria-label="Navegación móvil">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
            >
              <Icon size={18} className="nav-icon" />
              {label}
            </NavLink>
          ))}
          <NavLink
            to="/app/settings"
            className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}
          >
            <SettingsIcon size={18} className="nav-icon" />
            Ajustes
          </NavLink>
        </nav>
      </main>
    </div>
  );
}
