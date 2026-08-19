/**
 * Fase 13A — Clerk appearance derived from the active theme.
 *
 * Passed to <ClerkProvider appearance={...}> so EVERY Clerk surface — the
 * UserProfile card in Settings, the UserButton popover, the sign-in/sign-up
 * modals and the MFA session task — follows the doctor's chosen theme instead
 * of staying hardcoded dark on a light interface.
 */
import type { ClerkProviderProps } from '@clerk/react';
import { THEMES, resolveTheme, type ThemeKey } from './themes';

export type ClerkAppearance = ClerkProviderProps['appearance'];

export function clerkAppearance(key: ThemeKey | string | null | undefined): ClerkAppearance {
  const theme = THEMES[resolveTheme(key)];
  const t = theme.tokens;
  const dark = theme.mode === 'dark';
  return {
    variables: {
      fontFamily: "'Inter', system-ui, sans-serif",
      colorPrimary: t['--color-primary'],
      colorPrimaryForeground: t['--color-on-primary'],
      colorBackground: t['--color-surface'],
      colorForeground: t['--color-text'],
      colorMuted: t['--color-surface-2'],
      colorMutedForeground: t['--color-muted'],
      colorInput: t['--color-input-bg'],
      colorInputForeground: t['--color-text'],
      // Light shades on dark themes / dark shades on light themes (per Clerk docs):
      // drives borders, hover backgrounds and the focus ring base.
      colorNeutral: t['--color-text'],
      colorBorder: t['--color-border'],
      colorRing: t['--color-primary'],
      colorShadow: dark ? '#000000' : '#0F172A',
      colorModalBackdrop: dark ? '#010409' : '#0F172A',
      colorDanger: t['--color-danger'],
      colorSuccess: t['--color-success'],
      colorWarning: t['--color-gold'],
    },
  };
}
