// 后端 PDF 渲染脚本：用 Playwright/Chromium 把完整报告 HTML 转成真实 PDF。
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";

const [inputPath, outputPath] = process.argv.slice(2);

if (!inputPath || !outputPath) {
  console.error("Usage: node scripts/render_pdf.mjs <input.html> <output.pdf>");
  process.exit(2);
}

let browser;
try {
  browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({
    viewport: { width: 1240, height: 1754 },
    deviceScaleFactor: 1,
  });
  await page.goto(pathToFileURL(inputPath).href, { waitUntil: "networkidle" });
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: outputPath,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    headerTemplate: "<div></div>",
    footerTemplate:
      '<div style="font-size:8px;color:#8a94a6;width:100%;padding:0 13mm;display:flex;justify-content:space-between;"><span>Financial Agent PDF Export</span><span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    margin: { top: "12mm", right: "10mm", bottom: "14mm", left: "10mm" },
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
} finally {
  if (browser) {
    await browser.close();
  }
}
