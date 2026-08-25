import { useEffect, useRef, type ReactNode } from 'react';
import { Drawer } from 'vaul';
import { X } from 'lucide-react';
import { useTouchPresentation } from '../hooks/useMediaQuery';

interface SheetProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Ancho máximo del diálogo de escritorio. */
  maxWidth?: string;
  /**
   * Si el contenido tiene trabajo sin guardar, el arrastre para descartar se
   * desactiva. Un formulario clínico a medio escribir no puede irse con un
   * gesto accidental (§16: agencia con perdón — lo destructivo se confirma).
   */
  dismissibleByDrag?: boolean;
}

/**
 * Una superficie modal en dos gramáticas:
 *
 *  - Táctil → sheet inferior arrastrable (vaul). El contenido sigue al dedo
 *    1:1, el gesto proyecta su inercia para decidir si cierra o vuelve, y el
 *    borde resiste en vez de frenar en seco. Todo interrumpible.
 *  - Puntero fino → diálogo <dialog> nativo, que trae gratis la trampa de
 *    foco y el Escape, animado con muelle y ANCLADO al elemento que lo abrió,
 *    para que la relación espacial entre el botón y lo que aparece sea obvia.
 *
 * Entra y sale por el mismo camino en ambos casos (§7).
 */
export default function Sheet({
  isOpen,
  onClose,
  title,
  children,
  footer,
  maxWidth = '540px',
  dismissibleByDrag = true,
}: SheetProps) {
  const touch = useTouchPresentation();

  if (touch) {
    return (
      <Drawer.Root
        open={isOpen}
        onOpenChange={(open) => { if (!open) onClose(); }}
        dismissible={dismissibleByDrag}
      >
        <Drawer.Portal>
          <Drawer.Overlay className="sheet-overlay" />
          <Drawer.Content className="sheet-content" aria-describedby={undefined}>
            {/* El asidero dice "esto se arrastra" antes de que nadie lo intente. */}
            <div className="sheet-grabber" aria-hidden="true" />
            <div className="sheet-header">
              <Drawer.Title className="modal-title">{title}</Drawer.Title>
              <button className="btn btn-icon" onClick={onClose} aria-label="Cerrar" type="button">
                <X size={20} />
              </button>
            </div>
            <div className="sheet-body">{children}</div>
            {footer && <div className="sheet-footer">{footer}</div>}
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>
    );
  }

  return <AnchoredDialog {...{ isOpen, onClose, title, children, footer, maxWidth }} />;
}

/**
 * El diálogo de escritorio. Mantiene <dialog> por accesibilidad, pero el cierre
 * espera a que termine la animación de salida antes de llamar a close(), para
 * que la superficie no desaparezca de golpe.
 */
function AnchoredDialog({
  isOpen, onClose, title, children, footer, maxWidth,
}: Omit<SheetProps, 'dismissibleByDrag'>) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen && !dialog.open) {
      // Anclaje al origen (§7): la superficie crece desde el control que la
      // invocó, no desde el centro de la pantalla. El disparador es lo que
      // tenía el foco justo antes de abrir.
      //
      // Se escribe directo sobre el nodo en vez de pasar por estado: es un
      // valor que solo existe para el DOM, y así queda aplicado ANTES de que
      // el diálogo pinte, sin un render intermedio con el origen equivocado.
      const trigger = document.activeElement;
      let origin = '50% 50%';
      if (trigger instanceof HTMLElement && trigger !== document.body) {
        const r = trigger.getBoundingClientRect();
        const x = ((r.left + r.width / 2) / window.innerWidth) * 100;
        const y = ((r.top + r.height / 2) / window.innerHeight) * 100;
        origin = `${x.toFixed(1)}% ${y.toFixed(1)}%`;
      }
      if (contentRef.current) contentRef.current.style.transformOrigin = origin;
      dialog.showModal();
      document.body.style.overflow = 'hidden';
    } else if (!isOpen && dialog.open) {
      dialog.close();
      document.body.style.overflow = '';
    }

    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={(e) => { e.preventDefault(); onClose(); }}
      onClick={(e) => { if (e.target === dialogRef.current) onClose(); }}
      className="modal-dialog"
      style={{ maxWidth }}
    >
      <div
        ref={contentRef}
        className="modal-content glass-card modal-enter"
        onClick={(e) => e.stopPropagation()}
        role="document"
      >
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Cerrar" title="Cerrar" type="button">
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </dialog>
  );
}
