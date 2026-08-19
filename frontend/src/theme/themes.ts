/**
 * Fase 13A — typed, versioned theme catalog (frontend half).
 *
 * Five families × light/dark = 10 themes. Each theme overrides only the base
 * `--color-*` tokens (aliases like `--primary` resolve through them via var()).
 * Error/success keep their meaning across themes; the gold accent is constant.
 *
 * `clinical-teal-dark` is the default and its values are EXACTLY today's
 * index.css `:root`, so the current UI is visually identical.
 *
 * Keep the keys in lockstep with backend `app/core/themes.py`.
 */

export type ThemeKey =
  | 'clinical-teal-dark'
  | 'clinical-teal-light'
  | 'sapphire-dark'
  | 'sapphire-light'
  | 'indigo-dark'
  | 'indigo-light'
  | 'emerald-dark'
  | 'emerald-light'
  | 'plum-dark'
  | 'plum-light';

export const DEFAULT_THEME: ThemeKey = 'clinical-teal-dark';

export interface ThemeTokens {
  '--color-bg': string;
  '--color-surface': string;
  '--color-surface-2': string;
  '--color-border': string;
  '--color-primary': string;
  '--color-primary-hover': string;
  '--color-primary-tint': string;
  '--color-text': string;
  '--color-muted': string;
  '--color-muted-strong': string;
}

export interface ThemeDef {
  key: ThemeKey;
  /** Display name (family). */
  name: string;
  family: string;
  mode: 'dark' | 'light';
  /** Swatch color for the picker (the primary). */
  swatch: string;
  tokens: ThemeTokens;
}

// Shared neutral palettes (structure/typography/spacing never change — only color).
const DARK = {
  '--color-bg': '#0D1117',
  '--color-surface': '#161B22',
  '--color-surface-2': '#1C222B',
  '--color-border': '#2B3440',
  '--color-text': '#E6EDF3',
  '--color-muted': '#AAB6C3',
  '--color-muted-strong': '#C2CBD6',
} as const;

const LIGHT = {
  '--color-bg': '#F7F9FC',
  '--color-surface': '#FFFFFF',
  '--color-surface-2': '#F1F5F9',
  '--color-border': '#E2E8F0',
  '--color-text': '#0F172A',
  '--color-muted': '#64748B',
  '--color-muted-strong': '#475569',
} as const;

interface Primary {
  primary: string;
  hover: string;
  tint: string;
}

const FAMILIES: { family: string; name: string; dark: Primary; light: Primary }[] = [
  {
    family: 'clinical-teal',
    name: 'Clinical Teal',
    dark: { primary: '#00C2B8', hover: '#00D9CE', tint: 'rgba(0, 194, 184, 0.10)' },
    light: { primary: '#0D9488', hover: '#0F766E', tint: 'rgba(13, 148, 136, 0.10)' },
  },
  {
    family: 'sapphire',
    name: 'Sapphire',
    dark: { primary: '#2F81F7', hover: '#4C93FF', tint: 'rgba(47, 129, 247, 0.10)' },
    light: { primary: '#1D4ED8', hover: '#1E40AF', tint: 'rgba(29, 78, 216, 0.10)' },
  },
  {
    family: 'indigo',
    name: 'Indigo',
    dark: { primary: '#818CF8', hover: '#A5B4FC', tint: 'rgba(129, 140, 248, 0.10)' },
    light: { primary: '#4F46E5', hover: '#4338CA', tint: 'rgba(79, 70, 229, 0.10)' },
  },
  {
    family: 'emerald',
    name: 'Emerald',
    dark: { primary: '#34D399', hover: '#6EE7B7', tint: 'rgba(52, 211, 153, 0.10)' },
    light: { primary: '#059669', hover: '#047857', tint: 'rgba(5, 150, 105, 0.10)' },
  },
  {
    family: 'plum',
    name: 'Plum',
    dark: { primary: '#C084FC', hover: '#D8B4FE', tint: 'rgba(192, 132, 252, 0.10)' },
    light: { primary: '#9333EA', hover: '#7E22CE', tint: 'rgba(147, 51, 234, 0.10)' },
  },
];

function build(): Record<ThemeKey, ThemeDef> {
  const out = {} as Record<ThemeKey, ThemeDef>;
  for (const f of FAMILIES) {
    for (const mode of ['dark', 'light'] as const) {
      const key = `${f.family}-${mode}` as ThemeKey;
      const base = mode === 'dark' ? DARK : LIGHT;
      const p = mode === 'dark' ? f.dark : f.light;
      out[key] = {
        key,
        name: f.name,
        family: f.family,
        mode,
        swatch: p.primary,
        tokens: {
          ...base,
          '--color-primary': p.primary,
          '--color-primary-hover': p.hover,
          '--color-primary-tint': p.tint,
        },
      };
    }
  }
  return out;
}

export const THEMES: Record<ThemeKey, ThemeDef> = build();

export const THEME_ORDER: ThemeKey[] = [
  'clinical-teal-dark', 'clinical-teal-light',
  'sapphire-dark', 'sapphire-light',
  'indigo-dark', 'indigo-light',
  'emerald-dark', 'emerald-light',
  'plum-dark', 'plum-light',
];

export function isThemeKey(v: string | null | undefined): v is ThemeKey {
  return !!v && v in THEMES;
}

export function resolveTheme(v: string | null | undefined): ThemeKey {
  return isThemeKey(v) ? v : DEFAULT_THEME;
}
