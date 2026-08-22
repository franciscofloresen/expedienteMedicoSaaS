import { useCallback, useEffect, useRef, useState } from 'react';
import { Eraser } from 'lucide-react';

interface SignaturePadProps {
  label: string;
  onChange: (dataUrl: string) => void;
  required?: boolean;
}

const PAD_HEIGHT = 150;

export function SignaturePad({ label, onChange, required = false }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [hasSignature, setHasSignature] = useState(false);

  /** Size the backing store to the element's CSS box and reset the pen. */
  const prepare = useCallback((canvas: HTMLCanvasElement) => {
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(rect.width * ratio));
    canvas.height = Math.max(1, Math.round(PAD_HEIGHT * ratio));
    const context = canvas.getContext('2d');
    if (!context) return null;
    // Setting width/height already cleared the transform; scale once, then draw
    // in CSS pixels for the rest of the stroke.
    context.scale(ratio, ratio);
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, rect.width, PAD_HEIGHT);
    context.strokeStyle = '#17212b';
    context.lineWidth = 2.2;
    context.lineCap = 'round';
    context.lineJoin = 'round';
    return context;
  }, []);

  const resetCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (canvas) prepare(canvas);
  }, [prepare]);

  useEffect(() => {
    resetCanvas();
  }, [resetCanvas]);

  // Rotating an iPad (or opening the virtual keyboard) changes the canvas's CSS
  // width. The backing store does not follow on its own, so the browser scales
  // what is already drawn and every later stroke lands offset from the fingertip.
  // Re-measure on resize and repaint the existing signature into the new box.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let lastWidth = canvas.getBoundingClientRect().width;

    const handleResize = () => {
      const current = canvasRef.current;
      if (!current) return;
      const width = current.getBoundingClientRect().width;
      if (Math.abs(width - lastWidth) < 1) return;
      lastWidth = width;

      // Preserve whatever is on the pad across the re-measure.
      const snapshot = hasSignature ? current.toDataURL('image/png') : null;
      const context = prepare(current);
      if (context && snapshot) {
        const image = new Image();
        image.onload = () => context.drawImage(image, 0, 0, width, PAD_HEIGHT);
        image.src = snapshot;
      }
    };

    const observer =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(handleResize) : null;
    observer?.observe(canvas);
    window.addEventListener('orientationchange', handleResize);
    return () => {
      observer?.disconnect();
      window.removeEventListener('orientationchange', handleResize);
    };
  }, [hasSignature, prepare]);

  const point = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const start = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    // Stop the page from panning under the finger mid-signature on a tablet.
    event.preventDefault();
    // Capture keeps the stroke attached to this canvas even if the finger strays
    // past the border; not every engine implements it, so never let it throw.
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      /* capture is an optimisation, not a requirement */
    }
    drawing.current = true;
    const { x, y } = point(event);
    context.beginPath();
    context.moveTo(x, y);
    // A tap without movement should still leave a mark (a dot), the way a pen would.
    context.lineTo(x, y);
    context.stroke();
  };

  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    event.preventDefault();
    const { x, y } = point(event);
    context.lineTo(x, y);
    context.stroke();
  };

  const finish = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    drawing.current = false;
    try {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    } catch {
      /* see setPointerCapture above */
    }
    // JPEG keeps handwritten signatures small before they ever reach the API/S3 PDF.
    onChange(event.currentTarget.toDataURL('image/jpeg', 0.72));
    setHasSignature(true);
  };

  const clear = () => {
    resetCanvas();
    setHasSignature(false);
    onChange('');
  };

  return (
    <div className="form-group">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
        <label className="form-label">
          {label} {required && <span className="required-mark">*</span>}
        </label>
        {hasSignature && (
          <button type="button" className="btn btn-ghost" onClick={clear} style={{ padding: '0.25rem 0.55rem', fontSize: '0.78rem' }}>
            <Eraser size={13} /> Limpiar
          </button>
        )}
      </div>
      <canvas
        ref={canvasRef}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={finish}
        onPointerLeave={finish}
        aria-label={label}
        style={{
          width: '100%',
          height: PAD_HEIGHT,
          display: 'block',
          background: '#fff',
          border: `1px solid ${hasSignature ? 'var(--color-primary)' : 'var(--color-border)'}`,
          borderRadius: 'var(--radius-md)',
          touchAction: 'none',
          cursor: 'crosshair',
        }}
      />
      <small className="text-muted">Firma dentro del recuadro. Se comprime localmente y se sella por hash.</small>
    </div>
  );
}
