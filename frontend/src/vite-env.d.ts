/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_BASE_URL: string
  readonly VITE_APP_NAME: string
  readonly VITE_APP_VERSION: string
  readonly VITE_ENABLE_MOCK: string
  readonly VITE_ENABLE_STREAMING: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}