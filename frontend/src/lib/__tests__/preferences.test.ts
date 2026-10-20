import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PREFERENCES,
  parsePreferences,
} from '@/lib/preferences'

describe('preference validation', () => {
  it('returns defaults for missing or malformed storage values', () => {
    expect(parsePreferences(null)).toEqual(DEFAULT_PREFERENCES)
    expect(parsePreferences('{not json')).toEqual(DEFAULT_PREFERENCES)
    expect(parsePreferences('null')).toEqual(DEFAULT_PREFERENCES)
    expect(parsePreferences('"compact"')).toEqual(DEFAULT_PREFERENCES)
  })

  it('rejects unknown density and landing routes', () => {
    expect(
      parsePreferences('{"density":"tiny","defaultLanding":"/admin"}'),
    ).toEqual(DEFAULT_PREFERENCES)
  })

  it('accepts only supported presentation values', () => {
    expect(
      parsePreferences('{"density":"compact","defaultLanding":"/tickets"}'),
    ).toEqual({ density: 'compact', defaultLanding: '/tickets' })
  })
})
