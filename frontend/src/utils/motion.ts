/**
 * Fundaciones de movimiento — Fase 1 del rediseño (Apple design).
 *
 * Una sola fuente de verdad para los springs de la app. Apple sustituye
 * el trío físico (masa/rigidez/amortiguación) por dos parámetros:
 *
 *   - damping ratio → cuánto sobrepasa. 1.0 = sin rebote; <1.0 rebota.
 *   - response      → qué tan rápido alcanza el objetivo, en segundos.
 *                     NO es una duración: un spring no tiene duración fija.
 *
 * La API `bounce`/`duration` de motion mapea casi 1:1 con esos dos.
 *
 * Regla de casa: damping 1.0 por defecto. El rebote se reserva para cuando
 * el gesto YA traía inercia (un flick, un arrastre soltado). Un menú que
 * solo apareció no debe sobrepasar; una tarjeta que lanzaste, sí.
 */

export interface SpringConfig {
  type: 'spring';
  bounce: number;
  duration: number;
}

/** Por defecto para todo lo que no nació de un gesto con inercia. */
export const SPRING_UI: SpringConfig = { type: 'spring', bounce: 0, duration: 0.35 };

/** Reposicionar / mover un elemento (Apple: damping 1.0, response 0.4). */
export const SPRING_MOVE: SpringConfig = { type: 'spring', bounce: 0, duration: 0.4 };

/** Rotación (Apple: damping 0.8, response 0.4). */
export const SPRING_ROTATE: SpringConfig = { type: 'spring', bounce: 0.2, duration: 0.4 };

/** Cajón / sheet (Apple: damping 0.8, response 0.3). */
export const SPRING_SHEET: SpringConfig = { type: 'spring', bounce: 0.2, duration: 0.3 };

/** Aterrizaje de un flick — el gesto traía inercia, el rebote se gana. */
export const SPRING_MOMENTUM: SpringConfig = { type: 'spring', bounce: 0.2, duration: 0.35 };

/**
 * Proyección de inercia (§6). Dado la velocidad al soltar, ¿dónde se
 * detendría el elemento por sí solo? Se elige el punto de anclaje más
 * cercano a ESE punto proyectado, no al punto donde se soltó — eso es lo
 * que hace que un flick se sienta como un lanzamiento.
 *
 * Es la forma de decaimiento exponencial que usa Apple en el código de
 * ejemplo de *Designing Fluid Interfaces*, no la fórmula v²/(2a) de libro.
 *
 * @param initialVelocity px/s al soltar
 * @param decelerationRate 0.998 = scroll normal; 0.99 = más seco
 */
export function project(initialVelocity: number, decelerationRate = 0.998): number {
  return ((initialVelocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

/**
 * Rubber-banding (§9). Más allá del borde el elemento sigue al dedo cada
 * vez menos, en lugar de frenarse en seco. Un tope duro se lee como
 * "se congeló"; la resistencia progresiva se lee como "responde, pero
 * aquí ya no hay más".
 *
 * @param overshoot cuánto se pasó del límite, en px
 * @param dimension tamaño del eje sobre el que se arrastra
 */
export function rubberband(overshoot: number, dimension: number, constant = 0.55): number {
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
}

/**
 * Elige el punto de anclaje más cercano a un valor. Se usa con `project`:
 * `nearestSnapPoint(current + project(velocity), points)`.
 */
export function nearestSnapPoint(value: number, points: readonly number[]): number {
  return points.reduce((best, p) =>
    Math.abs(p - value) < Math.abs(best - value) ? p : best,
  );
}

/**
 * ¿El usuario pidió menos movimiento? Reduced motion NO significa sin
 * feedback: significa un equivalente no vestibular (cross-fade en vez de
 * deslizamiento, sin rebote). Los componentes consultan esto para elegir
 * la variante suave, no para apagarse.
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Variante sin desplazamiento ni rebote, para reduced motion. */
export const SPRING_REDUCED: SpringConfig = { type: 'spring', bounce: 0, duration: 0.2 };

/** Devuelve el spring pedido, o su equivalente suave si el usuario lo pidió. */
export function spring(config: SpringConfig): SpringConfig {
  return prefersReducedMotion() ? SPRING_REDUCED : config;
}
