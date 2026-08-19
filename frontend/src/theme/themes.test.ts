import { describe, it, expect, beforeEach } from 'vitest';
import { THEMES, THEME_ORDER, DEFAULT_THEME, resolveTheme, isThemeKey } from './themes';
import { applyThemeTokens, readCachedTheme, writeCachedTheme, themeCacheKey, getAppliedTheme, subscribeAppliedTheme } from './applyTheme';
import { clerkAppearance } from './clerkAppearance';

describe('theme catalog', () => {
  it('has exactly 10 themes (5 families × light/dark)', () => {
    expect(THEME_ORDER).toHaveLength(10);
    expect(Object.keys(THEMES)).toHaveLength(10);
  });

  it('the default is clinical-teal-dark and matches the current values exactly', () => {
    expect(DEFAULT_THEME).toBe('clinical-teal-dark');
    const t = THEMES['clinical-teal-dark'].tokens;
    // Guard: any change here would visually alter the current default UI.
    expect(t['--color-bg']).toBe('#0D1117');
    expect(t['--color-surface']).toBe('#161B22');
    expect(t['--color-primary']).toBe('#00C2B8');
    expect(t['--color-text']).toBe('#E6EDF3');
  });

  it('every theme defines the full token set, including mode-aware semantics', () => {
    for (const key of THEME_ORDER) {
      const t = THEMES[key].tokens;
      expect(t['--color-on-primary']).toBeTruthy();
      expect(t['--color-input-bg']).toBeTruthy();
      expect(t['--color-danger']).toBeTruthy();
      expect(t['--color-success']).toBeTruthy();
      expect(t['--color-gold']).toBeTruthy();
    }
    // Light themes flip the semantics to darker, legible-on-white values.
    expect(THEMES['clinical-teal-light'].tokens['--color-success']).not.toBe(
      THEMES['clinical-teal-dark'].tokens['--color-success'],
    );
    // The dark default keeps today's exact semantic values.
    expect(THEMES['clinical-teal-dark'].tokens['--color-danger']).toBe('#F85149');
    expect(THEMES['clinical-teal-dark'].tokens['--color-on-primary']).toBe('#04211F');
  });

  it('resolveTheme falls back to the default for unknown keys', () => {
    expect(resolveTheme('neon-pink')).toBe(DEFAULT_THEME);
    expect(resolveTheme(null)).toBe(DEFAULT_THEME);
    expect(resolveTheme('sapphire-light')).toBe('sapphire-light');
    expect(isThemeKey('plum-dark')).toBe(true);
    expect(isThemeKey('nope')).toBe(false);
  });
});

describe('applyThemeTokens', () => {
  it('writes the theme tokens and data-theme onto the target', () => {
    const el = document.createElement('div');
    applyThemeTokens('sapphire-dark', el);
    expect(el.getAttribute('data-theme')).toBe('sapphire-dark');
    expect(el.style.getPropertyValue('--color-primary')).toBe('#2F81F7');
    expect(el.style.colorScheme).toBe('dark');
  });

  it('applies the default for an invalid key', () => {
    const el = document.createElement('div');
    applyThemeTokens('bogus', el);
    expect(el.getAttribute('data-theme')).toBe('clinical-teal-dark');
  });

  it('exposes the document-applied theme through the external store', () => {
    let notified = 0;
    const unsubscribe = subscribeAppliedTheme(() => notified++);
    applyThemeTokens('plum-light'); // document-level apply
    expect(getAppliedTheme()).toBe('plum-light');
    expect(document.documentElement.getAttribute('data-theme-mode')).toBe('light');
    expect(notified).toBe(1);
    // Off-document applies (previews/tests) never touch the store.
    applyThemeTokens('sapphire-dark', document.createElement('div'));
    expect(getAppliedTheme()).toBe('plum-light');
    unsubscribe();
    applyThemeTokens(DEFAULT_THEME);
  });
});

describe('clerkAppearance', () => {
  it('maps the active theme onto Clerk variables (light themes are light)', () => {
    const light = clerkAppearance('clinical-teal-light');
    expect(light?.variables?.colorBackground).toBe('#FFFFFF');
    expect(light?.variables?.colorForeground).toBe('#0F172A');
    expect(light?.variables?.colorPrimary).toBe('#0D9488');
    const dark = clerkAppearance('clinical-teal-dark');
    expect(dark?.variables?.colorBackground).toBe('#161B22');
    expect(dark?.variables?.colorPrimaryForeground).toBe('#04211F');
  });

  it('falls back to the default theme for unknown keys', () => {
    expect(clerkAppearance('bogus')?.variables?.colorPrimary).toBe('#00C2B8');
  });
});

describe('theme cache (key only, per identity)', () => {
  beforeEach(() => localStorage.clear());

  it('is namespaced per identity so a shared device keeps identities separate', () => {
    expect(themeCacheKey('user_abc')).toBe('cmr:theme:user_abc');
    expect(themeCacheKey(null)).toBe('cmr:theme:anon');
  });

  it('roundtrips a valid key and falls back on an invalid stored value', () => {
    writeCachedTheme('user_1', 'emerald-light');
    expect(readCachedTheme('user_1')).toBe('emerald-light');
    localStorage.setItem('cmr:theme:user_1', 'garbage');
    expect(readCachedTheme('user_1')).toBe(DEFAULT_THEME);
    expect(readCachedTheme('other')).toBe(DEFAULT_THEME);
  });
});
