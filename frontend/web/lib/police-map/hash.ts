// The URL carries the selected place as #<id>, so a card can be shared. An id the map does
// not know, or a hash that is not an id at all, selects nothing.
export function idFromHash(hash: string, known: { has: (id: string) => boolean }): string | null {
  let id: string
  try {
    id = decodeURIComponent(hash.replace(/^#/, ''))
  } catch {
    return null
  }
  return known.has(id) ? id : null
}
