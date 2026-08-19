import puppeteer from 'puppeteer';

const [, , srcPath, outPath] = process.argv;
if (!srcPath || !outPath) {
  console.error('Usage: node render.mjs <input.html> <output.pdf>');
  process.exit(1);
}

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.goto('file:///' + srcPath.replace(/\\/g, '/'), { waitUntil: 'networkidle0' });
// Force print-media CSS (@media screen rules, e.g. the on-screen-only
// preview masthead/footer used by editable reports, must NOT render here).
await page.emulateMediaType('print');

// Reports can opt into a repeating (per-physical-page) header/footer and a
// flowing, non-paginated-by-div layout by embedding a JSON config in the
// page, e.g. <script type="application/json" id="pdf-header-footer">.
// Reports that don't include this tag keep the old behavior: one fixed
// A4-height .page div per section, zero margins, no repeating chrome.
const pdfConfig = await page.evaluate(() => {
  const el = document.getElementById('pdf-header-footer');
  if (!el) return null;
  try { return JSON.parse(el.textContent); } catch { return null; }
});

if (pdfConfig) {
  await page.pdf({
    path: outPath,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: pdfConfig.headerTemplate || '<span></span>',
    footerTemplate: pdfConfig.footerTemplate || '<span></span>',
    margin: pdfConfig.margin || { top: '30mm', right: '13mm', bottom: '16mm', left: '13mm' },
  });
} else {
  await page.pdf({
    path: outPath,
    format: 'A4',
    printBackground: true,
    margin: { top: '0mm', right: '0mm', bottom: '0mm', left: '0mm' },
  });
}

await browser.close();
console.log('OK');
