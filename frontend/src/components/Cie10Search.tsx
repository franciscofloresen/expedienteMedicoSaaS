import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cie10Api } from '../services/api';
import type { CIE10 } from '../types';
import { Search } from 'lucide-react';

const MIN_QUERY_LEN = 2;

interface Cie10SearchProps {
  onSelect: (code: string, description: string) => void;
  defaultValue?: string;
  name?: string;
  clearOnSelect?: boolean;
}

export default function Cie10Search({ onSelect, defaultValue, name, clearOnSelect = false }: Cie10SearchProps) {
  const [query, setQuery] = useState(defaultValue || '');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: results = [], isLoading, isError, error } = useQuery({
    queryKey: ['cie10', debouncedQuery],
    // React Query passes an AbortSignal; forwarding it cancels a stale in-flight request
    // as soon as the query text changes, so results never arrive out of order.
    queryFn: ({ signal }) => cie10Api.search(debouncedQuery, { signal }),
    enabled: debouncedQuery.length >= MIN_QUERY_LEN,
    // Session cache: identical searches within the session are served from cache
    // instead of re-hitting the API.
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  return (
    <div className="autocomplete">
      <div style={{ position: 'relative' }}>
        <Search size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-muted)', pointerEvents: 'none' }} />
        <input
          type="text"
          name={name}
          className="form-input"
          style={{ paddingLeft: '2.25rem' }}
          placeholder="Buscar enfermedad o código (ej. J00)"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          /* Se cierra de inmediato. Antes había un setTimeout de 200ms "para
             dar tiempo al clic", pero las opciones ya hacen preventDefault en
             onMouseDown, así que el blur ni siquiera llega a dispararse al
             elegir una. Los 200ms solo servían para que el menú se quedara
             colgado al salir del campo. */
          onBlur={() => setIsOpen(false)}
          autoComplete="off"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-label="Buscar diagnóstico CIE-10"
        />
      </div>

      {isOpen && query.length >= MIN_QUERY_LEN && (
        <div className="autocomplete-menu" role="listbox">
          {isLoading ? (
            <div className="autocomplete-empty">Buscando…</div>
          ) : results.length > 0 ? (
            results.map((item: CIE10) => (
              <div
                key={item.code}
                className="autocomplete-option"
                role="option"
                aria-selected={false}
                onMouseDown={(e) => e.preventDefault()} // Prevent blur before click
                onClick={() => {
                  const val = `${item.code} - ${item.description}`;
                  setQuery(clearOnSelect ? '' : val);
                  setIsOpen(false);
                  onSelect(item.code, item.description);
                }}
              >
                <span className="code">{item.code}</span>
                {item.description}
                {item.category && <div className="autocomplete-option-meta">{item.category}</div>}
              </div>
            ))
          ) : isError ? (
            <div className="autocomplete-empty" role="alert">
              {error instanceof Error ? error.message : 'No se pudo consultar el catálogo CIE-10.'}
            </div>
          ) : (
            <div className="autocomplete-empty">No se encontraron resultados</div>
          )}
        </div>
      )}
    </div>
  );
}
