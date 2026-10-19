/**
 * Timestamp helpers for the demonstration dataset.
 *
 * Fixture timestamps are generated relative to "now" at module load time so
 * dashboard charts and relative dates stay realistic without faking live
 * updates. The dataset itself is static — nothing refreshes on a timer.
 */

export function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

export function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString()
}

export function daysAgo(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString()
}

/** Internal SLA target helper: N hours in the future. */
export function hoursFromNow(hours: number): string {
  return new Date(Date.now() + hours * 3_600_000).toISOString()
}

/** Deterministic PRNG (mulberry32) so the generated fixtures are stable. */
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
