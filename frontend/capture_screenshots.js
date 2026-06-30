import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = path.join(process.cwd(), '..', 'docs', 'screenshots');

async function captureScreenshots() {
  // Ensure directory exists
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log('Starting browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2, // High DPI for good looking README images
  });
  const page = await context.newPage();

  try {
    // 1. Login Page
    console.log('Capturing Login Page...');
    await page.goto('http://localhost:5174/login');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login.png') });

    // Login Action
    console.log('Logging in as admin...');
    await page.fill('input[type="email"]', 'admin@docuquery.ai');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:5174/chat');
    await page.waitForLoadState('networkidle');

    // 2. Chat Page (with a response)
    console.log('Capturing Chat Page...');
    // Send a message to get a response
    await page.fill('textarea', 'What is the company overview for 2024?');
    await page.click('button:has(.lucide-send)');
    
    // Wait for the response to appear (assistant message with citations)
    // The response has role='assistant' and should contain a citation block or just take some time
    try {
      await page.waitForSelector('.citation', { timeout: 15000 });
      await page.waitForTimeout(1000); // give it a sec to finish rendering
    } catch (e) {
      await page.waitForTimeout(8000); // fallback wait
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'chat.png') });

    // 3. Documents Page (with upload modal)
    console.log('Capturing Documents Page...');
    await page.goto('http://localhost:5174/documents');
    await page.waitForLoadState('networkidle');
    // Click Upload Document button
    await page.click('button:has-text("Upload Document")');
    await page.waitForTimeout(500); // Wait for modal animation
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'documents.png') });

    // 4. Admin Panel
    console.log('Capturing Admin Panel...');
    await page.goto('http://localhost:5174/admin');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000); // Wait for data to load
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'admin.png') });

    // 5. Metrics Dashboard
    console.log('Capturing Metrics Dashboard...');
    await page.goto('http://localhost:5174/metrics');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500); // Wait for recharts animation
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'metrics.png') });

    console.log('All screenshots captured successfully!');
  } catch (error) {
    console.error('Error capturing screenshots:', error);
  } finally {
    await browser.close();
  }
}

captureScreenshots();
