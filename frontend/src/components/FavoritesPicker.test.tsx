import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import FavoritesPicker from './FavoritesPicker';
import type { MedicoFavorito } from '../types';

const favoritos: MedicoFavorito[] = [
  { id: '1', kind: 'receta', label: 'Paracetamol', texto: 'Paracetamol 500 mg c/8h x3d', creado_en: '', modificado_en: '' },
  { id: '2', kind: 'receta', label: 'Ibuprofeno', texto: 'Ibuprofeno 400 mg c/8h x5d', creado_en: '', modificado_en: '' },
];

describe('FavoritesPicker', () => {
  it('inserts a favorite\'s full text when its chip is clicked', async () => {
    const onInsert = vi.fn();
    render(<FavoritesPicker favoritos={favoritos} onInsert={onInsert} />);
    await userEvent.click(screen.getByRole('button', { name: 'Paracetamol' }));
    expect(onInsert).toHaveBeenCalledWith('Paracetamol 500 mg c/8h x3d');
  });

  it('shows an empty-state hint when there are no favorites', () => {
    render(<FavoritesPicker favoritos={[]} onInsert={vi.fn()} />);
    expect(screen.getByText(/Aún no tienes favoritos/i)).toBeInTheDocument();
  });

  it('disables save when there is nothing to save', () => {
    render(<FavoritesPicker favoritos={[]} onInsert={vi.fn()} onSaveCurrent={vi.fn()} canSave={false} />);
    expect(screen.getByRole('button', { name: /Guardar como favorito/i })).toBeDisabled();
  });

  it('calls onSaveCurrent when save is enabled and clicked', async () => {
    const onSaveCurrent = vi.fn();
    render(<FavoritesPicker favoritos={[]} onInsert={vi.fn()} onSaveCurrent={onSaveCurrent} canSave />);
    await userEvent.click(screen.getByRole('button', { name: /Guardar como favorito/i }));
    expect(onSaveCurrent).toHaveBeenCalledOnce();
  });
});
