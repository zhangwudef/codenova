/**
 * E2E 冒烟测试：验证前端基本可访问性
 *
 * 前置条件：本地 Demo 已启动（docker compose -f docker-compose.demo.yml up -d）
 */
import { test, expect } from '@playwright/test'

test.describe('CodeNova 冒烟测试', () => {
  test('首页可访问并显示标题', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('text=CodeNova')).toBeVisible()
  })

  test('显示「解析仓库」按钮', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('button:has-text("解析仓库")')).toBeVisible()
  })

  test('点击解析按钮弹出输入框', async ({ page }) => {
    await page.goto('/')
    await page.click('button:has-text("解析仓库")')
    await expect(page.locator('text=解析新仓库')).toBeVisible()
    await expect(page.locator('input[placeholder*="github.com"]')).toBeVisible()
  })

  test('窄屏显示提示', async ({ page }) => {
    await page.setViewportSize({ width: 800, height: 600 })
    await page.goto('/')
    await expect(page.locator('text=屏幕宽度不足')).toBeVisible()
  })
})
