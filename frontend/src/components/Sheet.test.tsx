import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Sheet from './Sheet';

/* jsdom reporta matchMedia siempre en false, así que estas pruebas ejercitan
   la rama de puntero fino: el diálogo anclado. */

beforeAll(() => {
  // jsdom no implementa el modal nativo; se suple lo justo para el contrato.
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function () { this.open = false; };
  }
});

describe('Sheet — diálogo anclado (puntero fino)', () => {
  it('no abre el diálogo mientras isOpen es false', () => {
    render(<Sheet isOpen={false} onClose={() => {}} title="Firmar nota">contenido</Sheet>);
    // Consulta directa al DOM: un <dialog> cerrado queda fuera del árbol de
    // accesibilidad, así que getByRole no lo encuentra — que es justo lo que
    // se quiere de un diálogo cerrado.
    expect(document.querySelector('dialog')!.open).toBe(false);
  });

  it('muestra título y contenido al abrir', () => {
    render(<Sheet isOpen onClose={() => {}} title="Firmar nota">Esta acción es irreversible</Sheet>);
    expect(screen.getByRole('heading', { name: 'Firmar nota' })).toBeInTheDocument();
    expect(screen.getByText('Esta acción es irreversible')).toBeInTheDocument();
  });

  it('el botón de cerrar avisa al consumidor', async () => {
    const onClose = vi.fn();
    render(<Sheet isOpen onClose={onClose} title="Firmar nota">contenido</Sheet>);
    await userEvent.click(screen.getByLabelText('Cerrar'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renderiza el pie solo cuando se le pasa', () => {
    const { rerender } = render(
      <Sheet isOpen onClose={() => {}} title="T">cuerpo</Sheet>,
    );
    expect(document.querySelector('.modal-footer')).toBeNull();
    rerender(
      <Sheet isOpen onClose={() => {}} title="T" footer={<button>Guardar</button>}>cuerpo</Sheet>,
    );
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeInTheDocument();
  });

  it('ancla el origen de la transformación al control que lo abrió (§7)', () => {
    // El disparador se coloca abajo a la derecha; la superficie debe crecer
    // desde ahí, no desde el centro de la pantalla.
    const trigger = document.createElement('button');
    document.body.appendChild(trigger);
    vi.spyOn(trigger, 'getBoundingClientRect').mockReturnValue({
      left: 768, top: 600, width: 32, height: 20,
      right: 800, bottom: 620, x: 768, y: 600, toJSON: () => ({}),
    } as DOMRect);
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, configurable: true });
    trigger.focus();

    render(<Sheet isOpen onClose={() => {}} title="T">cuerpo</Sheet>);

    const content = screen.getByRole('document') as HTMLElement;
    // (768 + 16) / 1024 = 76.6% ; (600 + 10) / 768 = 79.4%
    expect(content.style.transformOrigin).toBe('76.6% 79.4%');
    trigger.remove();
  });

  it('cae al centro cuando no hubo un disparador identificable', () => {
    document.body.focus();
    render(<Sheet isOpen onClose={() => {}} title="T">cuerpo</Sheet>);
    expect((screen.getByRole('document') as HTMLElement).style.transformOrigin).toBe('50% 50%');
  });

  it('libera el scroll del body al desmontarse', () => {
    const { unmount } = render(<Sheet isOpen onClose={() => {}} title="T">cuerpo</Sheet>);
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(document.body.style.overflow).toBe('');
  });
});
