// Vitest 全局测试设置
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// 每个测试用例后自动清理 DOM
afterEach(() => {
  cleanup()
  // 清除 localStorage
  localStorage.clear()
  // 重置所有 mock
  vi.restoreAllMocks()
})

// Mock matchMedia（部分组件可能用到）
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
})

// Mock ResizeObserver（@xyflow/react 等库依赖）
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock as any

// Mock IntersectionObserver
class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.IntersectionObserver = IntersectionObserverMock as any
