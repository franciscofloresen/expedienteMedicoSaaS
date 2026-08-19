/* eslint-disable react-hooks/set-state-in-effect */
/**
 * ThemeProvider — Fase 13A. Applies the authenticated user's visual theme.
 *
 * Order of truth: the server (`/auth/me`) wins. A per-identity local cache
 * (`cmr:theme:<clerk-sub>`, key only) anticipates the render to avoid a flash and
 * is reconciled with the server on load. Selecting a theme previews immediately,
 * then confirms on the server and reverts (throwing) if the server refuses.
 */
import { useCallback, useEffect, useLayoutEffect, useState, type ReactNode } from 'react';
import { useUser } from '@clerk/react';
import { authApi } from '../services/api';
import { applyThemeTokens, readCachedTheme, writeCachedTheme } from './applyTheme';
import { resolveTheme, type ThemeKey } from './themes';
import { ThemeContext } from './themeContextDef';

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { user, isSignedIn } = useUser();
  const sub = user?.id ?? null;
  const [theme, setThemeState] = useState<ThemeKey>(() => readCachedTheme(sub));

  // Apply before paint whenever the theme changes (no flash).
  useLayoutEffect(() => {
    applyThemeTokens(theme);
  }, [theme]);

  // When the identity becomes known, adopt that identity's cached theme.
  useEffect(() => {
    setThemeState(readCachedTheme(sub));
  }, [sub]);

  // Reconcile with the server (source of truth) once signed in.
  useEffect(() => {
    if (!isSignedIn || !sub) return;
    let cancelled = false;
    authApi
      .getProfile()
      .then((me: { tema?: string }) => {
        if (cancelled) return;
        const server = resolveTheme(me.tema);
        setThemeState(server);
        writeCachedTheme(sub, server);
      })
      .catch(() => {
        /* keep the cached/default theme if the read fails */
      });
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, sub]);

  const setTheme = useCallback(
    async (key: ThemeKey) => {
      const previous = theme;
      setThemeState(key); // optimistic preview
      writeCachedTheme(sub, key);
      try {
        await authApi.setTheme(key);
      } catch (e) {
        setThemeState(previous); // revert
        writeCachedTheme(sub, previous);
        throw e instanceof Error ? e : new Error('No se pudo guardar el tema.');
      }
    },
    [theme, sub],
  );

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
