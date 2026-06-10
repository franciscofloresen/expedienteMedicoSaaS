import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AuthProvider from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Pacientes from './pages/Pacientes';
import Expediente from './pages/Expediente';
import ExpedientesList from './pages/ExpedientesList';
import NotasList from './pages/NotasList';
import Auditoria from './pages/Auditoria';
import ErrorBoundary from './components/ErrorBoundary';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';
import Landing from './pages/Landing';
import Privacidad from './pages/Privacidad';

import { ToastProvider } from './contexts/ToastContext';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <ErrorBoundary>
            <BrowserRouter>
              <Routes>
                {/* Public routes */}
                <Route path="/" element={<Landing />} />
                <Route path="/privacidad" element={<Privacidad />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />

                {/* Protected routes — redirect to /login if not authenticated */}
                <Route element={<ProtectedRoute />}>
                  <Route path="/app" element={<Layout />}>
                    <Route index element={<Pacientes />} />
                    <Route path="expedientes" element={<ExpedientesList />} />
                    <Route path="notas" element={<NotasList />} />
                    <Route path="auditoria" element={<Auditoria />} />
                    <Route path="settings" element={<Settings />} />
                    <Route path="pacientes/:id" element={<Expediente />} />
                  </Route>
                </Route>
              </Routes>
            </BrowserRouter>
          </ErrorBoundary>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
