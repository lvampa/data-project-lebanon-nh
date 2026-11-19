// How a pin's calls compare with the other pins of its kind, from the counts in addresses.json.
// A road is ranked against roads and a place against places, since a road counts every call.
export function rankLine(count: number, counts: number[], kind: 'place' | 'road'): string {
  if (counts.length === 0) return ''
  const noun = kind === 'road' ? 'streets' : 'places'
  const above = counts.filter((c) => c > count).length
  // Only pins with fewer calls count as passed, so a tie does not flatter one.
  const below = counts.filter((c) => c < count).length
  const share = Math.round((100 * below) / counts.length)
  if (share < 50) return `Fewer calls than most ${noun} in Lebanon`
  return `More calls than ${share}% of ${noun} in Lebanon · #${above + 1} of ${counts.length.toLocaleString('en-US')}`
}
