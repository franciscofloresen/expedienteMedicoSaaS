import { useSyncExternalStore } from 'react';
import { ClerkProvider } from '@clerk/react';
import { esES } from '@clerk/localizations';
import App from './App.tsx';
import { getAppliedTheme, subscribeAppliedTheme } from './theme/applyTheme';
import { clerkAppearance } from './theme/clerkAppearance';

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!clerkPubKey) {
  throw new Error('Missing Publishable Key');
}

// ClerkProvider lives above ThemeProvider (which needs Clerk's useUser), so it
// follows the applied theme through the external store instead of the context.
// This themes every Clerk surface: UserProfile, UserButton, modals, MFA task.
export default function Root() {
  const theme = useSyncExternalStore(subscribeAppliedTheme, getAppliedTheme);
  return (
    <ClerkProvider
      publishableKey={clerkPubKey}
      afterSignOutUrl="/"
      localization={esES}
      taskUrls={{ 'setup-mfa': '/session-tasks/setup-mfa' }}
      appearance={clerkAppearance(theme)}
    >
      <App />
    </ClerkProvider>
  );
}
