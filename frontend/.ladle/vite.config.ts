import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

// Bare `@/*` imports mean different things in web/ and admin/, so resolve them
// against whichever workspace the importing file lives in.
const workspaceAtAlias = {
  name: 'workspace-at-alias',
  resolveId(id: string, importer?: string) {
    if (!id.startsWith('@/') || !importer) return
    const suffix = id.slice(2)
    if (importer.includes(`${path.sep}web${path.sep}`)) {
      return path.resolve(root, 'web', suffix)
    }
    if (importer.includes(`${path.sep}admin${path.sep}`)) {
      return path.resolve(root, 'admin', suffix)
    }
  },
}

export default defineConfig({
  plugins: [tailwindcss(), workspaceAtAlias],
  resolve: {
    alias: {
      '@project/ui': path.resolve(root, 'shared'),
    },
  },
})
