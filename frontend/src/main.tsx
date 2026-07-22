import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ClerkProvider } from '@clerk/react'
import { esES } from '@clerk/localizations'

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!clerkPubKey) {
  throw new Error("Missing Publishable Key");
}

createRoot(document.getElementById('root')!).render(
  <ClerkProvider
    publishableKey={clerkPubKey}
    afterSignOutUrl="/"
    localization={esES}
    taskUrls={{ 'setup-mfa': '/session-tasks/setup-mfa' }}
  >
    <App />
  </ClerkProvider>,
)
