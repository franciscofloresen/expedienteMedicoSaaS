import { test, expect, type Page } from '@playwright/test';

/**
 * Pase de tablet y móvil — flujo diario (entregable 2 del plan de pre-venta).
 *
 * The acceptance criterion is: a doctor signs a note end to end from a physical
 * iPad without zoom, without sideways scrolling, and without the virtual keyboard
 * hiding the field being typed into.
 *
 * Two tiers, mirroring e2e/README.md:
 *  - The layout contract below runs unauthenticated on the public shell plus a
 *    probe built from the app's own stylesheet, so it guards the rules that make
 *    the clinical screens work on a tablet without needing a Clerk test instance.
 *  - The auth-gated walk of the real flow is `test.fixme` alongside the other
 *    clinical flows, ready to switch on with the same Clerk wiring.
 */

const VIEWPORTS = {
  'iPad vertical (768×1024)': { width: 768, height: 1024 },
  'iPhone (390×844)': { width: 390, height: 844 },
};

/** The page itself must never scroll sideways at any width. */
async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    doc: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(overflow.body, 'body scrolls horizontally').toBeLessThanOrEqual(overflow.viewport);
  expect(overflow.doc, 'document scrolls horizontally').toBeLessThanOrEqual(overflow.viewport);
}

/**
 * Mount the clinical widgets that only exist behind auth, using the app's real
 * stylesheet, and measure them. This tests the CSS contract the daily flow
 * depends on — the part that actually broke on tablets — without a login.
 */
async function measureClinicalChrome(page: Page) {
  return page.evaluate(() => {
    const probe = document.createElement('div');
    probe.innerHTML = `
      <div class="tab-bar" id="r-tabs">
        <button class="tab active">Resumen</button>
        <button class="tab">Longitudinal</button>
        <button class="tab">Consultas</button>
        <button class="tab">Historia clínica</button>
        <button class="tab">Procedimientos</button>
        <button class="tab">Archivos</button>
        <button class="tab">Consentimientos</button>
      </div>
      <input class="form-input" id="r-input" />
      <textarea class="form-input" id="r-textarea"></textarea>
      <select class="form-input" id="r-select"></select>
      <button class="btn btn-primary" id="r-btn">Firmar</button>
      <div class="side-panel open" id="r-panel"></div>
      <div class="encounter-grid" id="r-grid"><div>a</div><div>b</div></div>
      <div class="table-card" id="r-tablecard"><table class="data-table"><tbody><tr><td>x</td></tr></tbody></table></div>
    `;
    document.body.appendChild(probe);
    const px = (el: Element, prop: string) =>
      parseFloat(getComputedStyle(el).getPropertyValue(prop));
    const q = (sel: string) => probe.querySelector(sel)!;
    const tabs = q('#r-tabs') as HTMLElement;
    const result = {
      viewport: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      tabBarOverflowX: getComputedStyle(tabs).overflowX,
      tabBarFitsViewport: tabs.clientWidth <= window.innerWidth,
      inputFontSize: px(q('#r-input'), 'font-size'),
      textareaFontSize: px(q('#r-textarea'), 'font-size'),
      selectFontSize: px(q('#r-select'), 'font-size'),
      inputMinHeight: px(q('#r-input'), 'min-height'),
      buttonMinHeight: px(q('#r-btn'), 'min-height'),
      tabMinHeight: px(q('.tab'), 'min-height'),
      panelWidth: (q('#r-panel') as HTMLElement).getBoundingClientRect().width,
      panelKeyboardRoom: px(q('#r-panel'), 'padding-bottom'),
      encounterGridColumns: getComputedStyle(q('#r-grid')).gridTemplateColumns.split(' ').length,
      tableCardOverflowX: getComputedStyle(q('#r-tablecard')).overflowX,
    };
    probe.remove();
    return result;
  });
}

for (const [name, viewport] of Object.entries(VIEWPORTS)) {
  test.describe(`layout on ${name}`, () => {
    test.use({ viewport });

    test('public shell never scrolls sideways', async ({ page }) => {
      await page.goto('/');
      await expectNoHorizontalScroll(page);
      await page.goto('/privacidad');
      await expectNoHorizontalScroll(page);
    });

    test('clinical chrome fits the viewport and is touch-sized', async ({ page }) => {
      await page.goto('/');
      const m = await measureClinicalChrome(page);

      // The page never widens, even with the expediente's seven tabs mounted.
      expect(m.bodyScrollWidth).toBeLessThanOrEqual(m.viewport);
      expect(m.tabBarFitsViewport).toBe(true);
      // Overflow is absorbed by the tab bar's own scroller.
      expect(m.tabBarOverflowX).toBe('auto');

      // 16px is the exact threshold below which iOS Safari zooms the page when a
      // field takes focus. Anything less breaks "firmar sin zoom" on a real iPad.
      expect(m.inputFontSize).toBeGreaterThanOrEqual(16);
      expect(m.textareaFontSize).toBeGreaterThanOrEqual(16);
      expect(m.selectFontSize).toBeGreaterThanOrEqual(16);

      // Touch targets.
      expect(m.inputMinHeight).toBeGreaterThanOrEqual(44);
      expect(m.buttonMinHeight).toBeGreaterThanOrEqual(44);
      expect(m.tabMinHeight).toBeGreaterThanOrEqual(44);

      // The note editor takes the full width and reserves room so the virtual
      // keyboard cannot be the thing covering the field in focus.
      expect(m.panelWidth).toBeLessThanOrEqual(m.viewport);
      expect(m.panelKeyboardRoom).toBeGreaterThan(100);

      // Two-column clinical layouts collapse; wide tables scroll inside the card.
      expect(m.encounterGridColumns).toBe(1);
      expect(m.tableCardOverflowX).toBe('auto');
    });
  });
}

test.describe('desktop is not touched by the tablet pass', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('desktop keeps its compact chrome', async ({ page }) => {
    await page.goto('/');
    const m = await measureClinicalChrome(page);
    // Compact desktop density is deliberate: the tablet rules must not leak up.
    expect(m.buttonMinHeight).toBeLessThan(44);
    expect(m.inputFontSize).toBeLessThan(16);
    expect(m.encounterGridColumns).toBe(2);
  });
});

test.describe('signing flow on a tablet (requires Clerk test auth + backend)', () => {
  // Turned on by the same wiring as clinical-flows.spec.ts (see e2e/README.md).
  test.fixme('agenda → paciente → nota → firmar → imprimir on 768px without sideways scroll', async () => {});
  test.fixme('the signature pad draws from touch events, not only mouse', async () => {});
  test.fixme('the focused note field stays visible with the virtual keyboard open', async () => {});
});
