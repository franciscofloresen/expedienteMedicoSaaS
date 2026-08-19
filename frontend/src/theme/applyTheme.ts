/**
 * Fase 13A — apply a theme's tokens to the document, and the no-flash local
 * cache. The cache stores ONLY the theme key (never PHI/clinical config), keyed
 * per identity so a shared device keeps identities separate.
 */
import { THEMES, DEFAULT_THEME, resolveTheme, type ThemeKey } from './themes';

export function applyThemeTokens(
  key: ThemeKey | string | null | undefined,
  target: HTMLElement = document.documentElement,
): ThemeKey {
  const resolved = resolveTheme(key);
  const theme = THEMES[resolved];
  for (const [name, value] of Object.entries(theme.tokens)) {
    target.style.setProperty(name, value);
  }
  target.setAttribute('data-theme', theme.key);
  target.setAttribute('data-theme-mode', theme.mode);
  // Native controls, scrollbars and form widgets follow the light/dark mode.
  target.style.colorScheme = theme.mode;
  if (target === document.documentElement) notifyApplied(resolved);
  return resolved;
}

/**
 * Tiny external store of the theme currently applied to the document, so code
 * ABOVE the ThemeProvider (ClerkProvider's `appearance` in main.tsx) can follow
 * the active theme via useSyncExternalStore.
 */
let appliedTheme: ThemeKey = DEFAULT_THEME;
const appliedListeners = new Set<() => void>();

function notifyApplied(key: ThemeKey): void {
  if (key === appliedTheme) return;
  appliedTheme = key;
  for (const l of appliedListeners) l();
}

export function getAppliedTheme(): ThemeKey {
  return appliedTheme;
}

export function subscribeAppliedTheme(listener: () => void): () => void {
  appliedListeners.add(listener);
  return () => appliedListeners.delete(listener);
}

const CACHE_PREFIX = 'cmr:theme:';

export function themeCacheKey(sub: string | null | undefined): string {
  return `${CACHE_PREFIX}${sub || 'anon'}`;
}

export function readCachedTheme(sub: string | null | undefined): ThemeKey {
  try {
    return resolveTheme(localStorage.getItem(themeCacheKey(sub)));
  } catch {
    return DEFAULT_THEME;
  }
}

export function writeCachedTheme(sub: string | null | undefined, key: ThemeKey): void {
  try {
    localStorage.setItem(themeCacheKey(sub), key);
  } catch {
    /* localStorage unavailable — the server remains the source of truth */
  }
}
