import { describe, it, expect } from 'vitest';
import { defaultChecklistItems } from './procedimientos';

describe('defaultChecklistItems', () => {
  it('returns pre-procedure items, all unchecked, with consent first', () => {
    const items = defaultChecklistItems('pre');
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((i) => i.completado === false)).toBe(true);
    expect(items[0].texto).toMatch(/Consentimiento/i);
  });

  it('returns different items for post-procedure (follow-up oriented)', () => {
    const pre = defaultChecklistItems('pre').map((i) => i.texto);
    const post = defaultChecklistItems('post').map((i) => i.texto);
    expect(post).not.toEqual(pre);
    expect(post.join(' ')).toMatch(/seguimiento/i);
  });
});
