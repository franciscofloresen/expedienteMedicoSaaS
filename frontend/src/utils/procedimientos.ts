/**
 * Default dermatology/aesthetics procedure checklists (Fase 13). Starting points
 * the doctor edits; pure so the seed content is testable and consistent.
 */
import type { ChecklistItem } from '../types';

export function defaultChecklistItems(momento: 'pre' | 'post'): ChecklistItem[] {
  const textos =
    momento === 'pre'
      ? [
          'Consentimiento informado firmado',
          'Identidad y sitio correctos confirmados',
          'Alergias y antecedentes revisados',
          'Antisepsia de la zona',
          'Material y equipo verificados',
        ]
      : [
          'Indicaciones de cuidado entregadas',
          'Signos de alarma explicados',
          'Cita de seguimiento agendada',
          'Fotografía de control (si aplica)',
        ];
  return textos.map((texto) => ({ texto, completado: false }));
}
