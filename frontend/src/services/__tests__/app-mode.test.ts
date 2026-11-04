import { describe, expect, it } from 'vitest'
import {
  DEV_API_BASE_URL,
  resolveApiBaseUrl,
  resolveDataMode,
} from '@/config/app-mode'

describe('data mode selection', () => {
  it('defaults to API mode when the setting is unset', () => {
    expect(resolveDataMode(undefined)).toBe('api')
    expect(resolveDataMode('')).toBe('api')
    expect(resolveDataMode('   ')).toBe('api')
  })

  it('keeps API mode explicit', () => {
    expect(resolveDataMode('api')).toBe('api')
    expect(resolveDataMode('API')).toBe('api')
  })

  it('only enables demo mode when named explicitly', () => {
    expect(resolveDataMode('demo')).toBe('demo')
    expect(resolveDataMode(' DEMO ')).toBe('demo')
    // Unknown values must not silently fall back to fixtures.
    expect(resolveDataMode('fixtures')).toBe('api')
    expect(resolveDataMode('local')).toBe('api')
  })
})

describe('API base URL resolution', () => {
  it('uses the local backend in development when unset', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe(DEV_API_BASE_URL)
    expect(resolveApiBaseUrl('', false)).toBe(DEV_API_BASE_URL)
  })

  it('uses the same origin in production when unset', () => {
    expect(resolveApiBaseUrl(undefined, true)).toBe('/api/v1')
  })

  it('normalizes an explicit origin', () => {
    expect(resolveApiBaseUrl('https://api.example.com/api/v1/', false)).toBe(
      'https://api.example.com/api/v1',
    )
    expect(resolveApiBaseUrl(' /api ', true)).toBe('/api')
  })
})
