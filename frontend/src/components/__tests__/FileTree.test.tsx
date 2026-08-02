/**
 * FileTree 组件单元测试
 *
 * 覆盖：空状态、文件/文件夹渲染、展开折叠、搜索过滤、文件选中
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FileTree from '../FileTree'
import type { FileNode } from '../../stores/repoStore'

// Mock repoStore —— FileTree 内部调用 useRepoStore
vi.mock('../../stores/repoStore', () => ({
  useRepoStore: vi.fn((selector) => {
    const state = {
      parseResult: {
        files: [
          { path: 'src/main.py', name: 'main.py' },
          { path: 'src/utils.py', name: 'utils.py' },
        ],
      },
      selectFile: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

// 测试数据
const mockNodes: FileNode[] = [
  {
    path: 'src',
    name: 'src',
    type: 'folder',
    children: [
      {
        path: 'src/main.py',
        name: 'main.py',
        type: 'file',
        language: 'python',
        symbolCount: 5,
      },
      {
        path: 'src/utils.py',
        name: 'utils.py',
        type: 'file',
        language: 'python',
        symbolCount: 2,
      },
    ],
  },
  {
    path: 'README.md',
    name: 'README.md',
    type: 'file',
    language: 'markdown',
    symbolCount: 0,
  },
]

describe('FileTree', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('nodes 为空时显示空状态提示', () => {
    render(<FileTree nodes={[]} onSelectFile={vi.fn()} />)
    expect(screen.getByText('暂无文件')).toBeInTheDocument()
    expect(screen.getByText('请先解析仓库')).toBeInTheDocument()
  })

  it('渲染顶层文件和文件夹', () => {
    render(<FileTree nodes={mockNodes} onSelectFile={vi.fn()} />)
    expect(screen.getByText('src')).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()
  })

  it('点击文件夹切换展开/折叠状态', () => {
    render(<FileTree nodes={mockNodes} onSelectFile={vi.fn()} />)
    // 初始状态：子文件不可见（文件夹未展开）
    expect(screen.queryByText('main.py')).not.toBeInTheDocument()

    // 点击 src 文件夹展开
    fireEvent.click(screen.getByText('src'))
    expect(screen.getByText('main.py')).toBeInTheDocument()
    expect(screen.getByText('utils.py')).toBeInTheDocument()

    // 再次点击折叠
    fireEvent.click(screen.getByText('src'))
    expect(screen.queryByText('main.py')).not.toBeInTheDocument()
  })

  it('搜索框输入后过滤文件树', () => {
    render(<FileTree nodes={mockNodes} onSelectFile={vi.fn()} />)

    // 先展开文件夹
    fireEvent.click(screen.getByText('src'))
    expect(screen.getByText('main.py')).toBeInTheDocument()

    // 搜索 "readme"
    const searchInput = screen.getByPlaceholderText('搜索文件...')
    fireEvent.change(searchInput, { target: { value: 'readme' } })

    // README.md 仍可见，src 文件夹下的文件被过滤
    expect(screen.getByText('README.md')).toBeInTheDocument()
  })

  it('点击文件节点触发 onSelectFile 回调', async () => {
    const { useRepoStore } = await import('../../stores/repoStore')
    const mockSelectFile = vi.fn()
    ;(useRepoStore as any).mockImplementation((selector: any) => {
      const state = {
        parseResult: { files: [{ path: 'README.md', name: 'README.md' }] },
        selectFile: mockSelectFile,
      }
      return selector ? selector(state) : state
    })

    const onSelectFile = vi.fn()
    render(<FileTree nodes={mockNodes} onSelectFile={onSelectFile} />)

    // 点击 README.md
    fireEvent.click(screen.getByText('README.md'))

    expect(mockSelectFile).toHaveBeenCalledWith({ path: 'README.md', name: 'README.md' })
    expect(onSelectFile).toHaveBeenCalledWith('README.md')
  })

  it('文件节点显示符号数量徽章', () => {
    render(<FileTree nodes={mockNodes} onSelectFile={vi.fn()} />)

    // 展开 src 文件夹
    fireEvent.click(screen.getByText('src'))

    // main.py 有 5 个符号
    expect(screen.getByText('5')).toBeInTheDocument()
    // utils.py 有 2 个符号
    expect(screen.getByText('2')).toBeInTheDocument()
  })
})
