// The API rejects page < 1 with a 422, so anything unparseable falls back to the first page.
export function pageFromParams(value: string | undefined): number {
  const page = Number(value)
  return Number.isInteger(page) && page > 0 ? page : 1
}
