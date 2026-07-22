import { TaskSetupMFA } from '@clerk/react';

export default function SetupMFA() {
  return (
    <main className="auth-page" aria-labelledby="mfa-title">
      <div style={{ width: '100%', maxWidth: 460, margin: '4rem auto' }}>
        <h1 id="mfa-title" style={{ textAlign: 'center' }}>Protege tu cuenta clínica</h1>
        <p className="text-muted" style={{ textAlign: 'center' }}>
          La verificación en dos pasos es obligatoria antes de acceder a expedientes.
        </p>
        <TaskSetupMFA redirectUrlComplete="/app" />
      </div>
    </main>
  );
}
