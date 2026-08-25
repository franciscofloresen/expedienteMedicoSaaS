import { describe, it, expect } from 'vitest';
import {
  project,
  rubberband,
  nearestSnapPoint,
  SPRING_UI,
  SPRING_SHEET,
  SPRING_MOMENTUM,
} from './motion';

describe('project — proyección de inercia (§6)', () => {
  it('sin velocidad no proyecta desplazamiento', () => {
    expect(project(0)).toBe(0);
  });

  it('proyecta en la dirección del gesto', () => {
    expect(project(500)).toBeGreaterThan(0);
    expect(project(-500)).toBeLessThan(0);
  });

  it('es simétrico respecto al signo de la velocidad', () => {
    expect(project(800)).toBeCloseTo(-project(-800), 10);
  });

  it('usa el decaimiento exponencial de Apple, no v²/(2a)', () => {
    // v/1000 · d/(1−d) con d = 0.998 → 500/1000 · 0.998/0.002 = 249.5
    expect(project(500)).toBeCloseTo(249.5, 6);
  });

  it('una tasa de deceleración menor aterriza más cerca', () => {
    expect(Math.abs(project(500, 0.99))).toBeLessThan(Math.abs(project(500, 0.998)));
  });
});

describe('rubberband — bordes blandos (§9)', () => {
  it('no resiste cuando no hay desbordamiento', () => {
    expect(rubberband(0, 400)).toBe(0);
  });

  it('siempre devuelve menos de lo que el dedo se movió', () => {
    for (const overshoot of [10, 50, 120, 400]) {
      expect(rubberband(overshoot, 400)).toBeLessThan(overshoot);
    }
  });

  it('resiste progresivamente: cuanto más lejos, menor la proporción seguida', () => {
    const cerca = rubberband(20, 400) / 20;
    const lejos = rubberband(300, 400) / 300;
    expect(lejos).toBeLessThan(cerca);
  });

  it('nunca frena en seco — sigue avanzando aunque sea poco', () => {
    expect(rubberband(1000, 400)).toBeGreaterThan(rubberband(500, 400));
  });

  it('conserva el signo del desbordamiento', () => {
    expect(rubberband(-80, 400)).toBeLessThan(0);
  });
});

describe('nearestSnapPoint', () => {
  it('elige el anclaje más cercano', () => {
    expect(nearestSnapPoint(0.6, [0, 0.5, 1])).toBe(0.5);
    expect(nearestSnapPoint(0.9, [0, 0.5, 1])).toBe(1);
  });

  it('combinado con project, un flick suave se pasa al siguiente anclaje', () => {
    const points = [0, 300, 600];
    // Soltado en 40px con 500px/s hacia abajo: proyecta a ~289 → ancla en 300.
    expect(nearestSnapPoint(40 + project(500), points)).toBe(300);
  });

  it('combinado con project, soltar casi sin velocidad vuelve al origen', () => {
    const points = [0, 300, 600];
    expect(nearestSnapPoint(40 + project(20), points)).toBe(0);
  });
});

describe('catálogo de springs', () => {
  it('el spring por defecto es críticamente amortiguado (sin sobrepaso)', () => {
    expect(SPRING_UI.bounce).toBe(0);
  });

  it('solo rebota lo que nació de un gesto con inercia', () => {
    expect(SPRING_SHEET.bounce).toBeGreaterThan(0);
    expect(SPRING_MOMENTUM.bounce).toBeGreaterThan(0);
  });

  it('la sheet responde más rápido que el movimiento genérico', () => {
    expect(SPRING_SHEET.duration).toBeLessThan(SPRING_UI.duration);
  });
});
