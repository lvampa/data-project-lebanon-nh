// How a place's calls compare with every pin on the map, from the counts in addresses.json.
export function rankLine(count: number, counts: number[]): string {
  if (counts.length === 0) return ''
  const above = counts.filter((c) => c > count).length
  // Only places with fewer calls count as passed, so a tie does not flatter a place.
  const below = counts.filter((c) => c < count).length
  const share = Math.round((100 * below) / counts.length)
  if (share < 50) return 'Fewer calls than most places in Lebanon'
  return `More calls than ${share}% of places in Lebanon · #${above + 1} of ${counts.length.toLocaleString('en-US')}`
}
