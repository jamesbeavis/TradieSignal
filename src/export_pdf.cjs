/**
 * Tradiesignal :: PDF export
 * Renders reports/report_print.html through Chromium's print engine so the
 * @page rules, web fonts and inline SVG charts all survive, then stamps a
 * running footer with page numbers.
 *
 * Browser resolution
 * ------------------
 * The first version hardcoded one machine's browser path, which cannot work
 * anywhere else. This tries, in order, and uses the first that launches:
 *
 *   1. $CHROME_PATH                 an explicit override, if you set one
 *   2. channel "chrome"             the system Google Chrome. GitHub's
 *                                   ubuntu-24.04 runners ship with it, so CI
 *                                   never has to download a browser at all.
 *   3. Playwright's bundled browser whatever `npx playwright install` fetched
 *   4. /opt/pw-browsers/chromium    the build sandbox's pre-installed copy
 *
 * Usage:  node src/export_pdf.cjs [output.pdf]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '../reports/report_print.html');
const OUT = process.argv[2] || path.resolve(__dirname, '../reports/Tradiesignal_Hunter_Report.pdf');

function candidates() {
  const list = [];
  if (process.env.CHROME_PATH) {
    list.push({ label: `CHROME_PATH (${process.env.CHROME_PATH})`,
                opts: { executablePath: process.env.CHROME_PATH } });
  }
  list.push({ label: 'system Google Chrome', opts: { channel: 'chrome' } });
  list.push({ label: "Playwright's bundled Chromium", opts: {} });
  if (fs.existsSync('/opt/pw-browsers/chromium')) {
    list.push({ label: 'sandbox Chromium', opts: { executablePath: '/opt/pw-browsers/chromium' } });
  }
  return list;
}

async function launchAny() {
  const failures = [];
  for (const c of candidates()) {
    try {
      const browser = await chromium.launch({ ...c.opts, args: ['--no-sandbox'] });
      console.log(`using ${c.label}`);
      return browser;
    } catch (err) {
      failures.push(`  - ${c.label}: ${String(err.message).split('\n')[0]}`);
    }
  }
  throw new Error('No usable browser found. Tried:\n' + failures.join('\n'));
}

(async () => {
  if (!fs.existsSync(SRC)) {
    throw new Error(`${SRC} not found — run build_report.py first`);
  }
  const browser = await launchAny();
  try {
    const page = await browser.newPage();
    await page.goto('file://' + SRC, { waitUntil: 'networkidle' });
    // Give the Google Fonts faces a beat to land before layout is frozen.
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.waitForTimeout(2500);
    await page.emulateMedia({ media: 'print' });

    const foot = `
      <div style="width:100%;box-sizing:border-box;font-family:monospace;font-size:7.5pt;
        line-height:1;color:#56675E;padding:0 13mm;">
        <span style="float:left">Tradiesignal &middot; Hunter Electrical Opportunity Report</span>
        <span style="float:right">Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
      </div>`;

    await page.pdf({
      path: OUT,
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<div></div>',
      footerTemplate: foot,
      margin: { top: '12mm', bottom: '14mm', left: '13mm', right: '13mm' },
    });
    console.log('wrote ' + OUT);
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
