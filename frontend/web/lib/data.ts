// Where the exported JSON lives. Local dev and the built site serve it from /data; a separate
// data host is set with NEXT_PUBLIC_DATA_URL when the build is deployed without data.
// An empty value, as an unset CI variable gives, counts as unset.
const DATA_URL = (process.env.NEXT_PUBLIC_DATA_URL || '/data').replace(/\/+$/, '')

export function dataUrl(filename: string): string {
  return `${DATA_URL}/${filename}`
}
