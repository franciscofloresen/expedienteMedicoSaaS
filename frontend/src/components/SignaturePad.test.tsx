import { fireEvent, render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SignaturePad } from './SignaturePad';

/**
 * Tablet behaviour of the signature pad (entregable 2 del plan de pre-venta).
 *
 * The pad is driven by Pointer Events so one code path serves mouse, stylus and
 * finger. jsdom has no 2D canvas, so we stub getContext and assert the drawing
 * calls the component makes — enough to catch the two regressions that actually
 * break signing on an iPad: a touch that leaves no stroke, and a re-measure
 * (rotation) that silently offsets every stroke afterwards.
 */

type StubContext = ReturnType<typeof makeContext>;

function makeContext() {
  return {
    scale: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    drawImage: vi.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    lineCap: '',
    lineJoin: '',
  };
}

let context: StubContext;
let resizeCallback: (() => void) | null = null;

beforeEach(() => {
  context = makeContext();
  resizeCallback = null;

  HTMLCanvasElement.prototype.getContext = vi.fn(() => context) as never;
  HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/jpeg;base64,STUB') as never;
  // jsdom reports a zero-sized box; give the canvas a real one so the component
  // can compute stroke coordinates.
  HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(() => ({
    x: 0, y: 0, top: 0, left: 0, right: 320, bottom: 150, width: 320, height: 150,
    toJSON: () => ({}),
  })) as never;

  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resizeCallback = callback;
      }
      observe() {}
      disconnect() {}
    },
  );
});

/** Pointer events are not constructible in jsdom; synthesise what React reads. */
function pointer(type: string, target: Element, x: number, y: number, pointerType: string) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(event, {
    pointerId: 1,
    pointerType,
    clientX: x,
    clientY: y,
    isPrimary: true,
  });
  fireEvent(target, event);
}

describe('SignaturePad on touch devices', () => {
  it('draws from touch pointer events, not only mouse', () => {
    render(<SignaturePad label="Firma del paciente" onChange={vi.fn()} />);
    const canvas = screen.getByLabelText('Firma del paciente');

    pointer('pointerdown', canvas, 20, 20, 'touch');
    pointer('pointermove', canvas, 60, 55, 'touch');
    pointer('pointerup', canvas, 60, 55, 'touch');

    expect(context.beginPath).toHaveBeenCalled();
    expect(context.moveTo).toHaveBeenCalledWith(20, 20);
    expect(context.lineTo).toHaveBeenCalledWith(60, 55);
    expect(context.stroke).toHaveBeenCalled();
  });

  it('leaves a mark for a tap with no movement, the way a pen would', () => {
    render(<SignaturePad label="Firma" onChange={vi.fn()} />);
    const canvas = screen.getByLabelText('Firma');

    pointer('pointerdown', canvas, 40, 40, 'touch');
    pointer('pointerup', canvas, 40, 40, 'touch');

    expect(context.lineTo).toHaveBeenCalledWith(40, 40);
    expect(context.stroke).toHaveBeenCalled();
  });

  it('emits the signature only after the stroke finishes', () => {
    const onChange = vi.fn();
    render(<SignaturePad label="Firma" onChange={onChange} />);
    const canvas = screen.getByLabelText('Firma');

    pointer('pointerdown', canvas, 10, 10, 'pen');
    pointer('pointermove', canvas, 30, 30, 'pen');
    expect(onChange).not.toHaveBeenCalled();

    pointer('pointerup', canvas, 30, 30, 'pen');
    expect(onChange).toHaveBeenCalledWith('data:image/jpeg;base64,STUB');
  });

  it('ignores movement that did not start with a pointer down', () => {
    render(<SignaturePad label="Firma" onChange={vi.fn()} />);
    const canvas = screen.getByLabelText('Firma');

    pointer('pointermove', canvas, 50, 50, 'touch');

    expect(context.lineTo).not.toHaveBeenCalled();
  });

  it('re-measures the backing store when the canvas is resized', () => {
    // Rotating an iPad changes the CSS width. Without a re-measure the browser
    // scales the old backing store and every later stroke lands off the fingertip.
    render(<SignaturePad label="Firma" onChange={vi.fn()} />);
    const canvas = screen.getByLabelText('Firma') as HTMLCanvasElement;

    const scaleCallsBefore = context.scale.mock.calls.length;
    HTMLCanvasElement.prototype.getBoundingClientRect = vi.fn(() => ({
      x: 0, y: 0, top: 0, left: 0, right: 700, bottom: 150, width: 700, height: 150,
      toJSON: () => ({}),
    })) as never;

    resizeCallback?.();

    expect(context.scale.mock.calls.length).toBeGreaterThan(scaleCallsBefore);
    expect(canvas.width).toBe(700);
  });

  it('does not re-measure when the width has not actually changed', () => {
    render(<SignaturePad label="Firma" onChange={vi.fn()} />);
    const scaleCallsBefore = context.scale.mock.calls.length;

    resizeCallback?.();

    expect(context.scale.mock.calls.length).toBe(scaleCallsBefore);
  });

  it('clears the pad and reports an empty signature', () => {
    const onChange = vi.fn();
    render(<SignaturePad label="Firma" onChange={onChange} />);
    const canvas = screen.getByLabelText('Firma');

    pointer('pointerdown', canvas, 10, 10, 'touch');
    pointer('pointerup', canvas, 10, 10, 'touch');
    onChange.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /Limpiar/i }));

    expect(onChange).toHaveBeenCalledWith('');
  });
});
