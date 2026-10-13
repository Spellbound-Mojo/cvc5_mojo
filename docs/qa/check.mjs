/* Browser checks for the built site, served beneath its deployment prefix. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat, mkdir } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = fileURLToPath(new URL('../..', import.meta.url));
const site = resolve(root, '.cache/docs-site');
const artifacts = resolve(root, '.cache/docs-browser');
await mkdir(artifacts, { recursive: true });
const prefix = '/cvc5_mojo/';
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    assert(pathname.startsWith(prefix));
    let path = resolve(site, pathname.slice(prefix.length));
    assert(path === site || path.startsWith(site + sep));
    if ((await stat(path)).isDirectory()) path = resolve(path, 'index.html');
    response.setHeader('Content-Type', types[extname(path)] || 'application/octet-stream');
    response.end(await readFile(path));
  } catch {
    response.statusCode = 404; response.end('Not found');
  }
});
await new Promise((done, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', done);
});
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  // Fail on an external request: equations, fonts and search must work locally.
  await context.route('**/*', route => {
    const url = route.request().url();
    if (!url.startsWith(origin + '/')) {
      errors.push(`External request: ${url}`); return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  page.on('requestfailed', request => errors.push(`Failed request: ${request.url()}`));
  const visit = async path => {
    await page.goto(origin + prefix + path, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    assert(await page.locator('main h1').count(), `Missing title: ${path}`);
  };
  const noOverflow = async () => assert(await page.evaluate(() =>
    document.documentElement.scrollWidth <= window.innerWidth + 1), `Horizontal page overflow: ${page.url()}`);
  const samples = new Set(['tutorials/first-query/', 'tutorials/transcendentals/exponential-logarithms/',
    'tutorials/transcendentals/bounds/', 'tutorials/transcendentals/inverse-derived/', 'tutorials/transcendentals/practical-cases/',
    'guides/cookbook/', 'guides/glossary/', 'tutorials/scheduling-app/model/', 'reference/term-manager/',
    'guides/python-migration/', 'guides/consumer-project/', 'guides/solver-options/', 'reference/options/']);
  // Discover every equation page from the generated inventory, so newly added
  // formulas cannot bypass validation by being absent from a hand-picked list.
  const inventory = JSON.parse(await readFile(resolve(site, 'search/search_index.json'), 'utf8'));
  for (const location of new Set(inventory.docs.map(doc => doc.location.split('#')[0]))) {
    const html = await readFile(resolve(site, location, 'index.html'), 'utf8');
    if (html.includes('class="math-display"')) samples.add(location);
  }
  for (const path of samples) {
    await visit(path);
    const equations = await page.locator('.math-display').count();
    if (equations) {
      assert.equal(await page.locator('.math-display .katex').count(), equations);
      assert.equal(await page.locator('.math-display math').count(), equations);
    }
    await noOverflow();
    await page.setViewportSize({ width: 390, height: 844 });
    await noOverflow();
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  await visit('guides/python-migration/');
  await page.screenshot({ path: resolve(artifacts, 'migration-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: resolve(artifacts, 'migration-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await visit('tutorials/transcendentals/bounds/');
  await page.screenshot({ path: resolve(artifacts, 'bounds-desktop.png'), fullPage: true });
  await page.locator('#theme-toggle').click();
  assert.equal(await page.locator('html').getAttribute('class'), 'dark');
  await page.reload({ waitUntil: 'networkidle' });
  assert.equal(await page.locator('html').getAttribute('class'), 'dark');
  await page.screenshot({ path: resolve(artifacts, 'bounds-dark.png'), fullPage: true });
  await page.locator('#theme-toggle').click();
  await page.keyboard.press('/');
  await page.waitForURL('**/search/');
  const query = page.locator('#search-query');
  await query.fill('logarithm');
  await page.locator('#search-results article').first().waitFor();
  assert(await page.locator('#search-results a').count());
  await query.fill('checkSat');
  await page.waitForFunction(() => [...document.querySelectorAll('#search-results a')].some(a => a.href.includes('/reference/')));
  await query.fill('title:');
  await page.waitForFunction(() => document.querySelector('#search-results').textContent.includes('such as checkSat'));
  await page.setViewportSize({ width: 390, height: 844 });
  await visit('tutorials/transcendentals/bounds/');
  await noOverflow();
  assert.equal(await page.locator('#site-nav').isVisible(), false);
  await page.locator('#nav-toggle').focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#nav-toggle').getAttribute('aria-expanded'), 'true');
  assert.equal(await page.locator('#site-nav').isVisible(), true);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#nav-toggle').getAttribute('aria-expanded'), 'false');
  assert(await page.locator('#nav-toggle').evaluate(element => element === document.activeElement));
  await page.screenshot({ path: resolve(artifacts, 'bounds-mobile.png'), fullPage: true });
  await page.locator('.math-display').first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: resolve(artifacts, 'equations-mobile.png') });
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  assert(await page.locator('#main').evaluate(element => element === document.activeElement));
  assert.deepEqual(errors, []);
  console.log('Browser checks passed: local assets, equations, desktop/mobile layout, theme, keyboard navigation, search.');
  console.log(`Screenshots: ${artifacts}`);
} finally {
  if (browser) await browser.close();
  await new Promise(done => server.close(done));
}
