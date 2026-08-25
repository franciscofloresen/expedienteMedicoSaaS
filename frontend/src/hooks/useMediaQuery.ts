import { useSyncExternalStore } from 'react';

/**
 * Suscripción a una media query. useSyncExternalStore en vez de useState +
 * useEffect para que el primer render ya tenga el valor correcto y no haya un
 * frame con la variante equivocada — que en una sheet significaría verla
 * aparecer centrada y saltar a inferior.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = (onChange: () => void) => {
    if (typeof window === 'undefined' || !window.matchMedia) return () => {};
    const mql = window.matchMedia(query);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  };
  const getSnapshot = () => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia(query).matches;
  };
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/**
 * ¿El usuario está tocando en vez de apuntando? Decide si una superficie se
 * presenta como sheet arrastrable desde abajo (dedo) o como diálogo anclado
 * al centro (ratón). Son gramáticas distintas, no la misma cosa reescalada.
 */
export function useTouchPresentation(): boolean {
  return useMediaQuery('(pointer: coarse), (max-width: 768px)');
}
