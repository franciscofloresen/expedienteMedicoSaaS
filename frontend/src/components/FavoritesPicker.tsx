/**
 * FavoritesPicker — one-click insertion of the doctor's saved snippets
 * (Fase 13 "Favoritos del médico"). Presentational and side-effect-free: the
 * parent owns fetching and the target field, so this is trivially unit-testable.
 */
import { Star, Plus } from 'lucide-react';
import type { MedicoFavorito } from '../types';

export default function FavoritesPicker({
  favoritos,
  onInsert,
  onSaveCurrent,
  canSave = false,
  label = 'Favoritos',
}: {
  favoritos: MedicoFavorito[];
  onInsert: (texto: string) => void;
  onSaveCurrent?: () => void;
  canSave?: boolean;
  label?: string;
}) {
  return (
    <div
      className="favorites-picker no-print"
      data-testid="favorites-picker"
      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}
    >
      <span className="overline" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.68rem' }}>
        <Star size={12} aria-hidden="true" /> {label}
      </span>

      {favoritos.length === 0 ? (
        <span className="text-muted" style={{ fontSize: '0.78rem' }}>Aún no tienes favoritos.</span>
      ) : (
        favoritos.map((f) => (
          <button
            key={f.id}
            type="button"
            className="btn btn-outline"
            style={{ padding: '0.2rem 0.55rem', fontSize: '0.78rem' }}
            title={f.texto}
            onClick={() => onInsert(f.texto)}
          >
            {f.label}
          </button>
        ))
      )}

      {onSaveCurrent && (
        <button
          type="button"
          className="btn btn-outline"
          style={{ padding: '0.2rem 0.55rem', fontSize: '0.78rem', marginLeft: 'auto' }}
          disabled={!canSave}
          title={canSave ? 'Guardar el texto actual como favorito' : 'Escribe algo primero'}
          onClick={onSaveCurrent}
        >
          <Plus size={12} /> Guardar como favorito
        </button>
      )}
    </div>
  );
}
