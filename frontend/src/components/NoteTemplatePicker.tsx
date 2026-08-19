/**
 * NoteTemplatePicker — apply a configurable note template into the editor
 * (Fase 13 "Plantillas configurables"). Presentational: the parent owns fetching
 * and applies the template's fields, so this is trivially unit-testable.
 */
import { LayoutTemplate, Plus } from 'lucide-react';
import type { NotaPlantilla } from '../types';

export default function NoteTemplatePicker({
  plantillas,
  onApply,
  onSaveCurrent,
  canSave = false,
}: {
  plantillas: NotaPlantilla[];
  onApply: (plantilla: NotaPlantilla) => void;
  onSaveCurrent?: () => void;
  canSave?: boolean;
}) {
  return (
    <div
      className="note-template-picker no-print"
      data-testid="note-template-picker"
      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}
    >
      <span className="overline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.68rem' }}>
        <LayoutTemplate size={12} aria-hidden="true" /> Plantillas
      </span>

      {plantillas.length === 0 ? (
        <span className="text-muted" style={{ fontSize: '0.78rem' }}>Aún no tienes plantillas.</span>
      ) : (
        plantillas.map((p) => (
          <button
            key={p.id}
            type="button"
            className="btn btn-outline"
            style={{ padding: '0.2rem 0.55rem', fontSize: '0.78rem' }}
            title={`Aplicar la plantilla "${p.nombre}" a esta nota`}
            onClick={() => onApply(p)}
          >
            {p.nombre}
          </button>
        ))
      )}

      {onSaveCurrent && (
        <button
          type="button"
          className="btn btn-outline"
          style={{ padding: '0.2rem 0.55rem', fontSize: '0.78rem', marginLeft: 'auto' }}
          disabled={!canSave}
          title={canSave ? 'Guardar los campos actuales como plantilla' : 'Escribe algo primero'}
          onClick={onSaveCurrent}
        >
          <Plus size={12} /> Guardar como plantilla
        </button>
      )}
    </div>
  );
}
