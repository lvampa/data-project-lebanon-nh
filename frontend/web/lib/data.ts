import fs from 'fs'
import path from 'path'

export function readDataFile<T>(filename: string): T {
  const filePath = path.join(process.cwd(), 'public', 'data', filename)
  const raw = fs.readFileSync(filePath, 'utf8')
  return JSON.parse(raw) as T
}
