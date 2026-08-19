import { describe, it, expect } from 'vitest';
import { groupPhotosForComparison } from './fotografias';
import type { FotografiaClinica } from '../types';

function foto(over: Partial<FotografiaClinica>): FotografiaClinica {
  return {
    id: Math.random().toString(),
    paciente_id: 'p',
    clinical_file_id: 'f',
    categoria: 'general',
    creado_en: '',
    modificado_en: '',
    ...over,
  } as FotografiaClinica;
}

describe('groupPhotosForComparison', () => {
  it('groups by grupo_comparacion and orders antes → despues within a group', () => {
    const fotos = [
      foto({ id: 'd', categoria: 'despues', grupo_comparacion: 'g1' }),
      foto({ id: 'a', categoria: 'antes', grupo_comparacion: 'g1' }),
    ];
    const groups = groupPhotosForComparison(fotos);
    expect(groups).toHaveLength(1);
    expect(groups[0].grupo).toBe('g1');
    expect(groups[0].fotos.map((f) => f.id)).toEqual(['a', 'd']); // antes before despues
  });

  it('puts named groups first and the ungrouped bucket last', () => {
    const fotos = [
      foto({ id: 'x' }), // no group
      foto({ id: 'y', grupo_comparacion: 'alpha' }),
    ];
    const groups = groupPhotosForComparison(fotos);
    expect(groups.map((g) => g.grupo)).toEqual(['alpha', null]);
  });

  it('treats blank/whitespace group as ungrouped', () => {
    const groups = groupPhotosForComparison([foto({ id: 'x', grupo_comparacion: '   ' })]);
    expect(groups[0].grupo).toBeNull();
  });
});
