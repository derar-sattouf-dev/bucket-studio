// Captures the README screenshots from a running Bucket Studio instance.
//
//   cd scripts/screenshots && pnpm install && pnpm capture
//
// Uses your installed Google Chrome (no browser download). Configure with env vars:
//   BASE_URL (default http://localhost:5173), BS_USERNAME / BS_PASSWORD (default: AUTH_* from ../../.env),
//   CHROME_CHANNEL (default "chrome"), ONLY (comma-separated shot names to capture, e.g. "playground"),
//   PLAYGROUND_PRESET_ID (preset to run in the Playground shot; default: the default preset).
// Seed demo data first: ./scripts/seed-demo.sh
import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../..");
const outDir = resolve(repoRoot, "docs/screenshots");

function envFileValue(name) {
    try {
        const line = readFileSync(resolve(repoRoot, ".env"), "utf8")
            .split("\n")
            .find((l) => l.startsWith(`${name}=`));
        return line?.slice(name.length + 1).trim();
    } catch {
        return undefined;
    }
}

const BASE_URL = process.env.BASE_URL ?? "http://localhost:5173";
const USERNAME = process.env.BS_USERNAME ?? envFileValue("AUTH_USERNAME");
const PASSWORD = process.env.BS_PASSWORD ?? envFileValue("AUTH_PASSWORD");
if (!USERNAME || !PASSWORD) throw new Error("Set BS_USERNAME / BS_PASSWORD or AUTH_* in .env");

const browser = await chromium.launch({ channel: process.env.CHROME_CHANNEL ?? "chrome" });
const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: "light",
});
const page = await context.newPage();

async function settle() {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(600); // let antd transitions finish
}

const only = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;

async function shot(name, action) {
    if (only && !only.has(name)) return;
    if (action) await action();
    await settle();
    await page.screenshot({ path: resolve(outDir, `${name}.png`) });
    console.log(`✓ ${name}.png`);
}

// ── Sign in ───────────────────────────────────────────────────────────────────
await page.goto(`${BASE_URL}/login`);
await shot("login");
await page.locator("#username").fill(USERNAME);
await page.locator("#password").fill(PASSWORD);
await page.getByRole("button", { name: /sign in|log in/i }).click();
await page.waitForURL("**/dashboard");

// ── Pages ─────────────────────────────────────────────────────────────────────
await shot("dashboard", () => page.goto(`${BASE_URL}/dashboard`));
await shot("images", () => page.goto(`${BASE_URL}/images`));
await shot("review", () => page.goto(`${BASE_URL}/review`));
await shot("presets", () => page.goto(`${BASE_URL}/presets`));
await shot("import", () => page.goto(`${BASE_URL}/import`));
await shot("jobs", () => page.goto(`${BASE_URL}/jobs`));
await shot("settings", () => page.goto(`${BASE_URL}/settings`));
await shot("settings-storage", () => page.goto(`${BASE_URL}/settings?tab=storage`));

// ── Playground: run the default preset on a sample photo (CC0, see docs/screenshots/CREDITS.md) ──
const SAMPLE_URL =
    "https://commons.wikimedia.org/wiki/Special:FilePath/" +
    "Chantilly_Porcelain_Factory_(French)_-_Teapot_-_1944.228.1.a_-_Cleveland_Museum_of_Art.jpg?width=1200";

await shot("playground", async () => {
    const response = await fetch(SAMPLE_URL, { headers: { "User-Agent": "bucket-studio-screenshots/0.1" } });
    if (!response.ok) throw new Error(`sample download failed: ${response.status}`);
    const sample = resolve(tmpdir(), "bucket-studio-teapot.jpg");
    writeFileSync(sample, Buffer.from(await response.arrayBuffer()));

    const preset = process.env.PLAYGROUND_PRESET_ID;
    await page.goto(`${BASE_URL}/playground${preset ? `?preset=${encodeURIComponent(preset)}` : ""}`);
    await page.locator("input[type=file]").setInputFiles(sample);
    await page.getByRole("button", { name: /\brun$/i }).click();
    await page.getByText("Processing time").waitFor({ timeout: 300_000 });
});

await browser.close();
