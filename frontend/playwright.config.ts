import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 *
 * 运行：npx playwright test
 * UI 模式：npx playwright test --ui
 * 报告：npx playwright show-report
 *
 * 前置条件：本地 Demo 已启动
 *   docker compose -f docker-compose.demo.yml up -d
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // E2E 测试串行执行，避免端口/索引冲突
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    timeout: 30000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // 本地启动前端开发服务器（如未运行）
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        reuseExistingServer: true,
        timeout: 60000,
      },
})
