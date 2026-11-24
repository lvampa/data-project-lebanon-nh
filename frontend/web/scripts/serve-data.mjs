// Serves the report-gen export on its own port, so local dev reads data from another origin,
// as the deployed site will.
import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import { dirname, join, normalize, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PORT = 4100
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../../data/export')

if (!existsSync(root)) {
    process.stderr.write(
        `No export at ${root}. Run bash scripts/generate_report.sh from the repo root.\n`,
    )
}

createServer((request, response) => {
    const path = normalize(decodeURIComponent(new URL(request.url, 'http://x').pathname))
    const file = join(root, path)
    response.setHeader('Access-Control-Allow-Origin', '*')
    const found = file.startsWith(root) && existsSync(file) && statSync(file).isFile()
    if (!found) {
        response.writeHead(404).end()
        return
    }
    response.writeHead(200, { 'Content-Type': 'application/json' })
    createReadStream(file).pipe(response)
}).listen(PORT, () => process.stdout.write(`Serving ${root} at http://localhost:${PORT}\n`))
