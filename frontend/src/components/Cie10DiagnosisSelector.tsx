import { Star, Trash2 } from 'lucide-react';
import Cie10Search from './Cie10Search';
import type { Cie10Certeza, NotaDiagnosticoCie10 } from '../types';

interface Cie10DiagnosisSelectorProps {
  value: NotaDiagnosticoCie10[];
  onChange: (value: NotaDiagnosticoCie10[]) => void;
  readOnly?: boolean;
}

export default function Cie10DiagnosisSelector({
  value,
  onChange,
  readOnly = false,
}: Cie10DiagnosisSelectorProps) {
  const addDiagnosis = (code: string, description: string) => {
    if (value.some((item) => item.code === code)) return;
    onChange([
      ...value,
      {
        code,
        description,
        es_principal: value.length === 0,
        certeza: 'presuntivo',
        orden: value.length,
      },
    ]);
  };

  const removeDiagnosis = (code: string) => {
    const removedWasPrincipal = value.find((item) => item.code === code)?.es_principal;
    const remaining = value
      .filter((item) => item.code !== code)
      .map((item, index) => ({ ...item, orden: index }));
    if (removedWasPrincipal && remaining.length > 0) remaining[0].es_principal = true;
    onChange(remaining);
  };

  const setPrincipal = (code: string) => {
    onChange(value.map((item) => ({ ...item, es_principal: item.code === code })));
  };

  const setCertainty = (code: string, certeza: Cie10Certeza) => {
    onChange(value.map((item) => (item.code === code ? { ...item, certeza } : item)));
  };

  return (
    <div className="cie10-diagnosis-selector">
      {!readOnly && <Cie10Search onSelect={addDiagnosis} clearOnSelect />}
      {value.length === 0 ? (
        <p className="text-muted" style={{ marginTop: '0.5rem' }}>
          Busca y agrega uno o más códigos; el primero se marcará como principal.
        </p>
      ) : (
        <div className="cie10-diagnosis-list">
          {value.map((item) => (
            <div className="cie10-diagnosis-item" key={item.code}>
              <button
                type="button"
                className={item.es_principal ? 'cie10-principal active' : 'cie10-principal'}
                onClick={() => setPrincipal(item.code)}
                disabled={readOnly}
                aria-label={`Marcar ${item.code} como diagnóstico principal`}
                title={item.es_principal ? 'Diagnóstico principal' : 'Marcar como principal'}
              >
                <Star size={14} fill={item.es_principal ? 'currentColor' : 'none'} />
              </button>
              <div className="cie10-diagnosis-copy">
                <strong className="mono">{item.code}</strong>
                <span>{item.description || 'Descripción no disponible'}</span>
                {item.es_principal && <small>Principal</small>}
              </div>
              <select
                className="form-input cie10-certainty"
                value={item.certeza}
                onChange={(event) => setCertainty(item.code, event.target.value as Cie10Certeza)}
                disabled={readOnly}
                aria-label={`Certeza de ${item.code}`}
              >
                <option value="presuntivo">Presuntivo</option>
                <option value="confirmado">Confirmado</option>
                <option value="descartado">Descartado</option>
              </select>
              {!readOnly && (
                <button
                  type="button"
                  className="btn-icon"
                  onClick={() => removeDiagnosis(item.code)}
                  aria-label={`Quitar ${item.code}`}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
