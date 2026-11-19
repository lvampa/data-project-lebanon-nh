// "11th", "22nd", "103rd".
export function ordinal(n: number): string {
  const lastTwo = n % 100
  if (lastTwo >= 11 && lastTwo <= 13) return `${n}th`
  const suffix = { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'
  return `${n}${suffix}`
}

// How a pin's calls compare with the other pins of its kind, from the counts in addresses.json.
// A street is ranked against streets and a place against places, since a street counts every call.
export function rankLine(count: number, counts: number[], kind: 'place' | 'road'): string {
  if (counts.length === 0) return ''
  const noun = kind === 'road' ? 'streets' : 'places'
  const above = counts.filter((c) => c > count).length
  // Only pins with fewer calls count as passed, so a tie does not flatter one.
  const below = counts.filter((c) => c < count).length
  const share = Math.round((100 * below) / counts.length)
  if (share < 50) return `Quieter than most ${noun} in Lebanon`
  return `${ordinal(above + 1)} busiest of ${counts.length.toLocaleString('en-US')} ${noun} in Lebanon`
}
