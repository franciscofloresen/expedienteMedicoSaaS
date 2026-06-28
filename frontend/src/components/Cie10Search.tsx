import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import type { CIE10 } from '../types';
import { Search } from 'lucide-react';

interface Cie10SearchProps {
  onSelect: (code: string, description: string) => void;
  defaultValue?: string;
  name: string;
}

export default function Cie10Search({ onSelect, defaultValue, name }: Cie10SearchProps) {
  const [query, setQuery] = useState(defaultValue || '');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['cie10', debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery || debouncedQuery.length < 2) return [];
      return await api.get<CIE10[]>(`/cie10?q=${debouncedQuery}`);
    },
    enabled: debouncedQuery.length >= 2,
  });

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ position: 'relative' }}>
        <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        <input
          type="text"
          name={name}
          className="form-input"
          style={{ paddingLeft: '2.25rem' }}
          placeholder="Buscar enfermedad o código CIE-10 (ej. J00)"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 200)} // delay to allow click
          autoComplete="off"
        />
      </div>

      {isOpen && query.length >= 2 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          marginTop: '0.25rem',
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-light)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-md)',
          zIndex: 10,
          maxHeight: '250px',
          overflowY: 'auto'
        }}>
          {isLoading ? (
            <div style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Buscando...</div>
          ) : results.length > 0 ? (
            results.map((item: CIE10) => (
              <div
                key={item.code}
                style={{ 
                  padding: '0.75rem 1rem', 
                  borderBottom: '1px solid var(--border-light)', 
                  cursor: 'pointer',
                  fontSize: '0.9rem'
                }}
                onMouseDown={(e) => e.preventDefault()} // Prevent blur before click
                onClick={() => {
                  const val = `${item.code} - ${item.description}`;
                  setQuery(val);
                  setIsOpen(false);
                  onSelect(item.code, item.description);
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-app)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <strong>{item.code}</strong> {item.description}
                {item.category && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.category}</div>}
              </div>
            ))
          ) : (
            <div style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>No se encontraron resultados</div>
          )}
        </div>
      )}
    </div>
  );
}
