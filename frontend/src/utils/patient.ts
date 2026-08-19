/**
 * Patient identity helpers (Fase 12 — wrong-patient prevention).
 *
 * Pure and side-effect-free so the identity banner can be unit-tested and so age
 * is computed the same way everywhere it is shown (capture, prescribe, sign).
 */

/** Full years between a date of birth (YYYY-MM-DD) and `now`. Returns null if unparseable. */
export function computeAgeYears(fechaNacimiento: string, now: Date = new Date()): number | null {
  if (!fechaNacimiento) return null;
  const dob = new Date(`${fechaNacimiento}T00:00:00`);
  if (Number.isNaN(dob.getTime())) return null;

  let age = now.getFullYear() - dob.getFullYear();
  const monthDiff = now.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < dob.getDate())) {
    age -= 1;
  }
  return age >= 0 ? age : null;
}

/** Human-readable sex label; unknown/other maps to "Otro". */
export function formatSexo(sexo: string | undefined | null): string {
  if (sexo === 'M') return 'Masculino';
  if (sexo === 'F') return 'Femenino';
  return 'Otro';
}

/** Compact identity string for logs/labels: "Nombre · 34 a · Femenino · CURP". */
export function formatIdentityLine(p: {
  nombre_completo: string;
  fecha_nacimiento: string;
  sexo?: string | null;
  curp?: string | null;
}, now: Date = new Date()): string {
  const age = computeAgeYears(p.fecha_nacimiento, now);
  const parts = [
    p.nombre_completo,
    age === null ? '' : `${age} a`,
    formatSexo(p.sexo),
    p.curp || 'sin CURP',
  ].filter(Boolean);
  return parts.join(' · ');
}
