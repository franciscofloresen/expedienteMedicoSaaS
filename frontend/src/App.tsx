import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Pacientes from './pages/Pacientes';
import Expediente from './pages/Expediente';
import ExpedientesList from './pages/ExpedientesList';
import NotasList from './pages/NotasList';
import ErrorBoundary from './components/ErrorBoundary';
import Settings from './pages/Settings';
import Auditoria from './pages/Auditoria';
import Landing from './pages/Landing';
import Privacidad from './pages/Privacidad';
import SeguridadCumplimiento from './pages/SeguridadCumplimiento';
import VerifyDocument from './pages/VerifyDocument';
import PrintDocument from './pages/PrintDocument';
import Onboarding from './pages/Onboarding';
import Agenda from './pages/Agenda';
import SetupMFA from './pages/SetupMFA';

import { ToastProvider } from './contexts/ToastContext';
import { useAuth } from '@clerk/react';
import type { ReactNode } from 'react';
import { setTokenFetcher } from './services/api';

const queryClient = new QueryClient();

function ApiSetup({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();
  
  setTokenFetcher(getToken);
  
  return <>{children}</>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ErrorBoundary>
          <ApiSetup>
            <BrowserRouter>
              <Routes>
                {/* Public routes */}
                <Route path="/" element={<Landing />} />
                <Route path="/privacidad" element={<Privacidad />} />
                <Route path="/seguridad-y-cumplimiento" element={<SeguridadCumplimiento />} />
                <Route path="/verify/:token" element={<VerifyDocument />} />
                <Route path="/session-tasks/setup-mfa" element={<SetupMFA />} />

                {/* Protected routes — handled by Clerk */}
                <Route element={<ProtectedRoute />}>
                  <Route path="/onboarding" element={<Onboarding />} />
                  <Route path="/app" element={<Layout />}>
                    <Route index element={<Pacientes />} />
                    <Route path="agenda" element={<Agenda />} />
                    <Route path="expedientes" element={<ExpedientesList />} />
                    <Route path="notas" element={<NotasList />} />
                    <Route path="settings" element={<Settings />} />
                    <Route path="auditoria" element={<Auditoria />} />
                    <Route path="pacientes/:id" element={<Expediente />} />
                    <Route path="documentos/:kind/:id/print" element={<PrintDocument />} />
                  </Route>
                </Route>
              </Routes>
            </BrowserRouter>
          </ApiSetup>
        </ErrorBoundary>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default App;
