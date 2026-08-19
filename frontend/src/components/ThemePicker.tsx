/**
 * ThemePicker — Fase 13A settings grid. Ten themes with a swatch, name and mode;
 * the current one is marked. Selecting previews immediately (ThemeProvider) and
 * confirms on the server, reverting with a message if it fails.
 */
import { useState } from 'react';
import { Check, Palette } from 'lucide-react';
import { useTheme } from '../theme/useTheme';
import { THEMES, THEME_ORDER, type ThemeKey } from '../theme/themes';
import { useToast } from '../hooks/useToast';

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
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
        <Palette size={20} color="var(--color-primary)" />
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Apariencia</h2>
      </div>
      <p className="text-muted" style={{ marginTop: 0, fontSize: '0.9rem' }}>
        Elige el tema de la interfaz. Sólo cambia colores; los documentos impresos y firmados
        se mantienen neutrales. La preferencia es tuya y te sigue en cualquier dispositivo.
      </p>

      <div
        role="radiogroup"
        aria-label="Tema de la interfaz"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '0.75rem', marginTop: '1rem' }}
      >
        {THEME_ORDER.map((key) => {
          const t = THEMES[key];
          const selected = key === theme;
          return (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={saving !== null}
              onClick={() => choose(key)}
              style={{
                textAlign: 'left',
                border: selected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                borderRadius: '10px',
                padding: '0.7rem',
                background: t.tokens['--color-surface'],
                color: t.tokens['--color-text'],
                cursor: saving ? 'wait' : 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ display: 'inline-flex', gap: '4px' }}>
                  <span style={{ width: 16, height: 16, borderRadius: '50%', background: t.swatch, display: 'inline-block' }} />
                  <span style={{ width: 16, height: 16, borderRadius: '4px', background: t.tokens['--color-bg'], border: `1px solid ${t.tokens['--color-border']}`, display: 'inline-block' }} />
                </span>
                {selected && <Check size={15} color={t.swatch} />}
              </div>
              <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>{t.name}</div>
              <div style={{ fontSize: '0.72rem', opacity: 0.7 }}>{t.mode === 'dark' ? 'Oscuro' : 'Claro'}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
