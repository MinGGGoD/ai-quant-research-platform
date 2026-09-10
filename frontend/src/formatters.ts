import { ApiError } from './api'

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function humanize(value: string): string {
  return value.replaceAll('_', ' ')
}

export function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? '{}'
  } catch {
    return '{}'
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.requestId
      ? `${error.message} Request ID: ${error.requestId}`
      : error.message
  }
  return 'The research data could not be loaded.'
}
