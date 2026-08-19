import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import NoteTemplatePicker from './NoteTemplatePicker';
import type { NotaPlantilla } from '../types';

const plantillas: NotaPlantilla[] = [
  { id: 't1', nombre: 'Dermatoscopia', campos: { exploracion_fisica: 'Lesión...' }, version: 1, creado_en: '', modificado_en: '' },
  { id: 't2', nombre: 'Control estético', campos: { plan_tratamiento: 'Seguimiento' }, version: 2, creado_en: '', modificado_en: '' },
];

describe('NoteTemplatePicker', () => {
  it('applies the whole template when its chip is clicked', async () => {
    const onApply = vi.fn();
    render(<NoteTemplatePicker plantillas={plantillas} onApply={onApply} />);
    await userEvent.click(screen.getByRole('button', { name: 'Dermatoscopia' }));
    expect(onApply).toHaveBeenCalledWith(plantillas[0]);
  });

  it('shows an empty-state hint when there are no templates', () => {
    render(<NoteTemplatePicker plantillas={[]} onApply={vi.fn()} />);
    expect(screen.getByText(/Aún no tienes plantillas/i)).toBeInTheDocument();
  });

  it('disables save when there is nothing to save', () => {
    render(<NoteTemplatePicker plantillas={[]} onApply={vi.fn()} onSaveCurrent={vi.fn()} canSave={false} />);
    expect(screen.getByRole('button', { name: /Guardar como plantilla/i })).toBeDisabled();
  });

  it('calls onSaveCurrent when save is enabled and clicked', async () => {
    const onSaveCurrent = vi.fn();
    render(<NoteTemplatePicker plantillas={[]} onApply={vi.fn()} onSaveCurrent={onSaveCurrent} canSave />);
    await userEvent.click(screen.getByRole('button', { name: /Guardar como plantilla/i }));
    expect(onSaveCurrent).toHaveBeenCalledOnce();
  });
});
