/**
 * Group clinical photos for before/after comparison (Fase 13). Pure and tested.
 * Photos sharing a `grupo_comparacion` are grouped; within a group they are
 * ordered antes → despues → seguimiento → general so a comparison reads left→right.
 * Photos with no group fall under a single "Sin grupo" bucket.
 */
import type { FotografiaClinica, FotoCategoria } from '../types';

export interface PhotoGroup {
  grupo: string | null;
  fotos: FotografiaClinica[];
}

const CATEGORY_ORDER: Record<FotoCategoria, number> = {
  antes: 0,
  despues: 1,
  seguimiento: 2,
  general: 3,
};

export function groupPhotosForComparison(fotos: FotografiaClinica[]): PhotoGroup[] {
  const byGroup = new Map<string | null, FotografiaClinica[]>();
  for (const f of fotos) {
    const key = f.grupo_comparacion?.trim() || null;
    const list = byGroup.get(key) ?? [];
    list.push(f);
    byGroup.set(key, list);
  }

  const groups: PhotoGroup[] = [];
  for (const [grupo, list] of byGroup.entries()) {
    list.sort((a, b) => CATEGORY_ORDER[a.categoria] - CATEGORY_ORDER[b.categoria]);
    groups.push({ grupo, fotos: list });
  }

  // Named comparison groups first (alphabetical), the ungrouped bucket last.
  groups.sort((a, b) => {
    if (a.grupo === null) return 1;
    if (b.grupo === null) return -1;
    return a.grupo.localeCompare(b.grupo);
  });
  return groups;
}
