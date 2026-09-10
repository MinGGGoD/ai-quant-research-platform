import 'server-only'

const DEFAULT_SERVER_API_BASE_URL = 'http://localhost:8000'

export function getServerApiBaseUrl(): string {
  return (
    process.env.BACKEND_INTERNAL_URL ?? DEFAULT_SERVER_API_BASE_URL
  ).replace(/\/$/, '')
}
