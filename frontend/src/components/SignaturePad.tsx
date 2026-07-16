import { useEffect, useRef, useState } from 'react';
import { Eraser } from 'lucide-react';

interface SignaturePadProps {
  label: string;
  onChange: (dataUrl: string) => void;
  required?: boolean;
}

export function SignaturePad({ label, onChange, required = false }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [hasSignature, setHasSignature] = useState(false);

  const resetCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(rect.width * ratio));
    canvas.height = Math.max(1, Math.round(150 * ratio));
    const context = canvas.getContext('2d');
    if (!context) return;
    context.scale(ratio, ratio);
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, rect.width, 150);
    context.strokeStyle = '#17212b';
    context.lineWidth = 2.2;
    context.lineCap = 'round';
    context.lineJoin = 'round';
  };

  useEffect(() => {
    resetCanvas();
  }, []);

  const point = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const start = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    drawing.current = true;
    const { x, y } = point(event);
    context.beginPath();
    context.moveTo(x, y);
  };

  const move = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    const { x, y } = point(event);
    context.lineTo(x, y);
    context.stroke();
  };

  const finish = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    drawing.current = false;
    event.currentTarget.releasePointerCapture(event.pointerId);
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
        aria-label={label}
        style={{
          width: '100%',
          height: 150,
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
