import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const foundations = readFileSync(resolve(here, 'foundations.css'), 'utf8');
const index = readFileSync(resolve(here, '../index.css'), 'utf8');

/** Nombres de token declarados en un archivo (`--x: valor`). */
function declarados(css: string): Set<string> {
  return new Set([...css.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map(m => m[1]));
}

/** Nombres de token consumidos vía var(--x). */
function consumidos(css: string): Set<string> {
  return new Set([...css.matchAll(/var\((--[\w-]+)/g)].map(m => m[1]));
}

const enFoundations = declarados(foundations);
const enIndex = declarados(index);
const disponibles = new Set([...enFoundations, ...enIndex]);

describe('contrato de las fundaciones', () => {
  it('todo token que index.css consume está declarado en algún sitio', () => {
    const huerfanos = [...consumidos(index)].filter(t => !disponibles.has(t));
    expect(huerfanos).toEqual([]);
  });

  it('cada paso de la escala tipográfica trae SU tracking y SU leading', () => {
    // Un tamaño sin ajuste óptico emparejado es exactamente lo que la escala
    // existe para evitar: el mismo letter-spacing sirviendo a 9px y a 27px.
    const pasos = [...enFoundations]
      .filter(t => /^--text-[\w]+$/.test(t) && !/-track$|-lead$/.test(t));
    expect(pasos.length).toBeGreaterThan(5);
    for (const paso of pasos) {
      expect(enFoundations.has(`${paso}-track`), `${paso} sin tracking`).toBe(true);
      expect(enFoundations.has(`${paso}-lead`), `${paso} sin leading`).toBe(true);
    }
  });

  it('--ease-exit es el inverso exacto de --ease-enter (§7)', () => {
    const bezier = (nombre: string) => {
      const m = foundations.match(new RegExp(`${nombre}:\\s*cubic-bezier\\(([^)]+)\\)`));
      if (!m) throw new Error(`${nombre} no encontrado`);
      return m[1].split(',').map(n => parseFloat(n.trim()));
    };
    const [x1, y1, x2, y2] = bezier('--ease-enter');
    const salida = bezier('--ease-exit');
    // El inverso de (x1,y1,x2,y2) es (1-x2, 1-y2, 1-x1, 1-y1). Con tolerancia:
    // el CSS lleva 0.68 y 1 - 0.32 da 0.6799999999999999 en coma flotante.
    const esperado = [1 - x2, 1 - y2, 1 - x1, 1 - y1];
    salida.forEach((v, i) => expect(v).toBeCloseTo(esperado[i], 6));
  });

  it('el modo claro redefine el canto del material', () => {
    // En claro, un canto blanco sobre un material casi blanco es invisible.
    const bloqueClaro = foundations.slice(foundations.indexOf("data-theme-mode='light'"));
    expect(bloqueClaro).toMatch(/--material-edge:\s*rgba\(15, 23, 42/);
  });

  it('el root tipográfico es relativo, no un px fijo', () => {
    // Un `font-size: 14px` en html ignora el tamaño de letra del usuario.
    const htmlRule = index.slice(index.indexOf('\nhtml {'), index.indexOf('\nbody {'));
    expect(htmlRule).toMatch(/font-size:\s*87\.5%/);
    expect(htmlRule).not.toMatch(/font-size:\s*\d+px/);
  });

  it('las tres señales de accesibilidad del sistema están atendidas', () => {
    for (const señal of [
      'prefers-reduced-motion: reduce',
      'prefers-reduced-transparency: reduce',
      'prefers-contrast: more',
    ]) {
      expect(index).toContain(`@media (${señal})`);
    }
  });

  it('la impresión fija el estado final y apaga toda animación', () => {
    // Los contenedores animados arrancan en opacity 0 con fill-mode `both`. Si
    // la instantánea de impresión se toma antes de que terminen, una receta o
    // una nota firmada salen desvanecidas o en blanco. Es un requisito legal,
    // no estético.
    const bloquePrint = index.slice(index.indexOf('@media print'));
    expect(bloquePrint).toMatch(/animation:\s*none\s*!important/);
    expect(bloquePrint).toMatch(/opacity:\s*1\s*!important/);
    expect(bloquePrint).toMatch(/transform:\s*none\s*!important/);
    // El wash ambiental es un background-image: el reset de color no lo quita.
    expect(bloquePrint).toMatch(/background-image:\s*none\s*!important/);
  });

  it('los overrides de tokens de tema llevan !important o no aplican', () => {
    // applyThemeTokens escribe los tokens de color inline sobre <html>, y el
    // inline gana a cualquier regla de hoja. Un override sin !important dentro
    // de las media queries de accesibilidad es código muerto silencioso.
    const bloques = [...index.matchAll(
      /@media \(prefers-(?:reduced-transparency|contrast)[^)]*\) \{([\s\S]*?)\n\}/g,
    )].map(m => m[1]);
    expect(bloques.length).toBe(2);
    for (const bloque of bloques) {
      for (const [, decl] of bloque.matchAll(/(--color-[\w-]+:[^;]+);/g)) {
        expect(decl, `override sin !important: ${decl}`).toContain('!important');
      }
    }
  });
});
