import { createContext } from 'react';
import type { ThemeKey } from './themes';

export interface ThemeContextValue {
  theme: ThemeKey;
  /** Preview + persist a theme. Rejects (and reverts) if the server refuses. */
  setTheme: (key: ThemeKey) => Promise<void>;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
