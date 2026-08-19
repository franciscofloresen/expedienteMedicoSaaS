/**
 * ThemePicker — Fase 13A settings card. Each theme renders a miniature mockup
 * of the app (sidebar, topbar, note card, primary button) painted with that
 * theme's own tokens, so the doctor sees exactly what they're choosing.
 * Selecting previews immediately (ThemeProvider) and confirms on the server,
 * reverting with a message if it fails.
 */
import { useState } from 'react';
import { Check, Loader2, Moon, Palette, Sun } from 'lucide-react';
import { useTheme } from '../theme/useTheme';
import { THEMES, THEME_ORDER, type ThemeDef, type ThemeKey } from '../theme/themes';
import { useToast } from '../hooks/useToast';

function ThemePreview({ t }: { t: ThemeDef }) {
  const c = t.tokens;
  return (
    <span className="theme-preview" aria-hidden="true" style={{ background: c['--color-bg'] }}>
      <span
        className="theme-preview-sidebar"
        style={{ background: c['--color-surface'], borderColor: c['--color-border'] }}
      >
        <span className="theme-preview-nav" style={{ background: c['--color-primary-tint'] }}>
          <span className="theme-preview-bar" style={{ background: c['--color-primary'] }} />
        </span>
        <span className="theme-preview-bar" style={{ background: c['--color-border'], width: '80%' }} />
        <span className="theme-preview-bar" style={{ background: c['--color-border'], width: '65%' }} />
        <span className="theme-preview-bar" style={{ background: c['--color-border'], width: '72%' }} />
      </span>
      <span className="theme-preview-main">
        <span
          className="theme-preview-card"
          style={{ background: c['--color-surface'], borderColor: c['--color-border'] }}
        >
          <span className="theme-preview-bar" style={{ background: c['--color-text'], width: '55%', opacity: 0.85 }} />
          <span className="theme-preview-bar" style={{ background: c['--color-muted'], width: '90%', opacity: 0.55 }} />
          <span className="theme-preview-bar" style={{ background: c['--color-muted'], width: '70%', opacity: 0.55 }} />
          <span className="theme-preview-btn" style={{ background: c['--color-primary'] }} />
        </span>
      </span>
    </span>
  );
}

export default function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const { showToast } = useToast();
  const [saving, setSaving] = useState<ThemeKey | null>(null);

  const choose = async (key: ThemeKey) => {
    if (key === theme || saving) return;
    setSaving(key);
    try {
      await setTheme(key);
      showToast('Tema actualizado.', 'success');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'No se pudo guardar el tema.', 'error');
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="glass-card animate-fade-in" style={{ animationDelay: '0.2s' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
        <div style={{ backgroundColor: 'var(--color-primary-tint)', padding: '0.5rem', borderRadius: 'var(--radius-md)', color: 'var(--color-primary)', display: 'inline-flex' }}>
          <Palette size={24} />
        </div>
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Apariencia</h2>
      </div>
      <p className="text-muted" style={{ marginTop: 0, fontSize: '0.9rem' }}>
        Elige el tema de la interfaz. Sólo cambia colores; los documentos impresos y firmados
        se mantienen neutrales. La preferencia es tuya y te sigue en cualquier dispositivo.
      </p>

      <div role="radiogroup" aria-label="Tema de la interfaz" className="theme-grid">
        {THEME_ORDER.map((key) => {
          const t = THEMES[key];
          const selected = key === theme;
          const isSaving = saving === key;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={`${t.name} — ${t.mode === 'dark' ? 'oscuro' : 'claro'}`}
              disabled={saving !== null}
              onClick={() => choose(key)}
              className={`theme-card${selected ? ' selected' : ''}`}
            >
              <ThemePreview t={t} />
              {(selected || isSaving) && (
                <span
                  className="theme-check"
                  style={{ background: t.swatch, color: t.tokens['--color-on-primary'] }}
                >
                  {isSaving ? (
                    <Loader2 size={13} style={{ animation: 'spin 0.8s linear infinite' }} />
                  ) : (
                    <Check size={13} strokeWidth={3} />
                  )}
                </span>
              )}
              <span className="theme-card-meta">
                <span className="theme-card-swatch" style={{ background: t.swatch }} />
                <span style={{ minWidth: 0 }}>
                  <span className="theme-card-name" style={{ display: 'block' }}>{t.name}</span>
                  <span className="theme-card-mode">
                    {t.mode === 'dark' ? <Moon size={11} /> : <Sun size={11} />}
                    {t.mode === 'dark' ? 'Oscuro' : 'Claro'}
                  </span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
