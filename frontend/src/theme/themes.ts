/**
 * Fase 13A — typed, versioned theme catalog (frontend half).
 *
 * Five families × light/dark = 10 themes. Each theme overrides only the base
 * `--color-*` tokens (aliases like `--primary` resolve through them via var()).
 * Semantic colors (danger/success/gold) keep their meaning across themes but
 * carry a per-mode value so they stay legible on light backgrounds.
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
  '--color-border-strong': string;
  '--color-glass': string;
  '--color-input-bg': string;
  '--color-input-bg-focus': string;
  '--color-primary': string;
  '--color-primary-hover': string;
  '--color-primary-tint': string;
  '--color-on-primary': string;
  '--color-text': string;
  '--color-muted': string;
  '--color-muted-strong': string;
  '--color-danger': string;
  '--color-danger-tint': string;
  '--color-success': string;
  '--color-success-tint': string;
  '--color-gold': string;
  '--color-gold-tint': string;
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
  '--color-border-strong': '#3A4654',
  '--color-glass': 'rgba(13, 17, 23, 0.85)',
  '--color-input-bg': '#0F151D',
  '--color-input-bg-focus': '#101923',
  '--color-text': '#E6EDF3',
  '--color-muted': '#AAB6C3',
  '--color-muted-strong': '#C2CBD6',
  '--color-danger': '#F85149',
  '--color-danger-tint': 'rgba(248, 81, 73, 0.10)',
  '--color-success': '#3FB950',
  '--color-success-tint': 'rgba(63, 185, 80, 0.10)',
  '--color-gold': '#D4A843',
  '--color-gold-tint': 'rgba(212, 168, 67, 0.10)',
} as const;

const LIGHT = {
  '--color-bg': '#F7F9FC',
  '--color-surface': '#FFFFFF',
  '--color-surface-2': '#F1F5F9',
  '--color-border': '#E2E8F0',
  '--color-border-strong': '#94A3B8',
  '--color-glass': 'rgba(247, 249, 252, 0.85)',
  '--color-input-bg': '#FFFFFF',
  '--color-input-bg-focus': '#FFFFFF',
  '--color-text': '#0F172A',
  '--color-muted': '#64748B',
  '--color-muted-strong': '#475569',
  '--color-danger': '#DC2626',
  '--color-danger-tint': 'rgba(220, 38, 38, 0.08)',
  '--color-success': '#059669',
  '--color-success-tint': 'rgba(5, 150, 105, 0.10)',
  '--color-gold': '#A16207',
  '--color-gold-tint': 'rgba(161, 98, 7, 0.10)',
} as const;

interface Primary {
  primary: string;
  hover: string;
  tint: string;
  /** Text on a solid primary background (buttons, calendar events). */
  onPrimary: string;
}

const FAMILIES: { family: string; name: string; dark: Primary; light: Primary }[] = [
  {
    family: 'clinical-teal',
    name: 'Clinical Teal',
    dark: { primary: '#00C2B8', hover: '#00D9CE', tint: 'rgba(0, 194, 184, 0.10)', onPrimary: '#04211F' },
    light: { primary: '#0D9488', hover: '#0F766E', tint: 'rgba(13, 148, 136, 0.10)', onPrimary: '#FFFFFF' },
  },
  {
    family: 'sapphire',
    name: 'Sapphire',
    dark: { primary: '#2F81F7', hover: '#4C93FF', tint: 'rgba(47, 129, 247, 0.10)', onPrimary: '#05152B' },
    light: { primary: '#1D4ED8', hover: '#1E40AF', tint: 'rgba(29, 78, 216, 0.10)', onPrimary: '#FFFFFF' },
  },
  {
    family: 'indigo',
    name: 'Indigo',
    dark: { primary: '#818CF8', hover: '#A5B4FC', tint: 'rgba(129, 140, 248, 0.10)', onPrimary: '#0D0F2B' },
    light: { primary: '#4F46E5', hover: '#4338CA', tint: 'rgba(79, 70, 229, 0.10)', onPrimary: '#FFFFFF' },
  },
  {
    family: 'emerald',
    name: 'Emerald',
    dark: { primary: '#34D399', hover: '#6EE7B7', tint: 'rgba(52, 211, 153, 0.10)', onPrimary: '#032115' },
    light: { primary: '#059669', hover: '#047857', tint: 'rgba(5, 150, 105, 0.10)', onPrimary: '#FFFFFF' },
  },
  {
    family: 'plum',
    name: 'Plum',
    dark: { primary: '#C084FC', hover: '#D8B4FE', tint: 'rgba(192, 132, 252, 0.10)', onPrimary: '#20092F' },
    light: { primary: '#9333EA', hover: '#7E22CE', tint: 'rgba(147, 51, 234, 0.10)', onPrimary: '#FFFFFF' },
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
          '--color-on-primary': p.onPrimary,
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
