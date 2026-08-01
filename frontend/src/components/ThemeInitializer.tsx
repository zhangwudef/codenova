/**
 * 主题初始化组件: 在 App 渲染前应用主题到 document
 * 避免 FOUC（Flash of Unstyled Content）
 */
import { useEffect } from 'react'
import { useThemeStore } from '../stores/themeStore'

export function ThemeInitializer() {
  const applyToDocument = useThemeStore((s) => s.applyToDocument)
  const resolved = useThemeStore((s) => s.resolved)

  useEffect(() => {
    applyToDocument()
  }, [applyToDocument, resolved])

  return null
}
