// What a list of top rows leaves out, so the rows add up to the number above them.
export function remainder(rows: [string, number][], total: number): number {
  const shown = rows.reduce((sum, [, n]) => sum + n, 0)
  return Math.max(0, total - shown)
}
