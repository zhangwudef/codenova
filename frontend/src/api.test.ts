/**
 * API 客户端测试
 * 覆盖: API Key 头注入、错误处理、端点调用
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, setApiKey, hasApiKey } from './api'

describe('API Key 管理', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('默认无 API Key', () => {
    expect(hasApiKey()).toBe(false)
  })

  it('setApiKey 持久化到 localStorage', () => {
    setApiKey('test-key-123')
    expect(hasApiKey()).toBe(true)
    expect(localStorage.getItem('codenova_api_key')).toBe('test-key-123')
  })

  it('setApiKey(null) 清除 API Key', () => {
    setApiKey('test-key-123')
    setApiKey(null)
    expect(hasApiKey()).toBe(false)
    expect(localStorage.getItem('codenova_api_key')).toBeNull()
  })
})

describe('API 请求', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('未设置 API Key 时不附加 X-API-Key 头', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await api.healthReady()

    expect(fetchSpy).toHaveBeenCalledOnce()
    const [, init] = fetchSpy.mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers['X-API-Key']).toBeUndefined()
  })

  it('设置 API Key 后附加 X-API-Key 头', async () => {
    setApiKey('secret-key-456')

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await api.healthReady()

    expect(fetchSpy).toHaveBeenCalledOnce()
    const [, init] = fetchSpy.mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers['X-API-Key']).toBe('secret-key-456')
  })

  it('HTTP 错误时抛出包含 detail 的 Error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid API key.' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    await expect(api.healthReady()).rejects.toThrow('Invalid API key.')
  })

  it('HTTP 错误且无 detail 时回退到状态码', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Not Found', { status: 404 })
    )

    await expect(api.healthReady()).rejects.toThrow(/请求失败 404/)
  })

  it('indexRepo 发送正确的 POST 请求体', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          repo_url: 'test',
          total_files: 1,
          total_chunks: 1,
          total_embeddings: 1,
          collection_name: 'test',
          elapsed_seconds: 0.1,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )

    await api.indexRepo('https://github.com/x/y', 'main', 100, 'ast')

    expect(fetchSpy).toHaveBeenCalledOnce()
    const [url, init] = fetchSpy.mock.calls[0]
    expect(url).toContain('/rag/index')
    expect(init?.method).toBe('POST')
    const body = JSON.parse(init?.body as string)
    expect(body).toEqual({
      repo_url: 'https://github.com/x/y',
      branch: 'main',
      max_files: 100,
      chunk_strategy: 'ast',
    })
  })
})
