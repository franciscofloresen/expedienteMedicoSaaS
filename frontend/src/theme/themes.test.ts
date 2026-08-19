import { describe, it, expect, beforeEach } from 'vitest';
import { THEMES, THEME_ORDER, DEFAULT_THEME, resolveTheme, isThemeKey } from './themes';
import { applyThemeTokens, readCachedTheme, writeCachedTheme, themeCacheKey } from './applyTheme';

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
