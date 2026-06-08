import type { StorybookConfig } from '@storybook/react-vite'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

const config: StorybookConfig = {
  stories: [
    '../shared/components/**/*.stories.@(ts|tsx)',
    '../web/components/**/*.stories.@(ts|tsx)',
    '../admin/components/**/*.stories.@(ts|tsx)',
  ],
  addons: [
    '@storybook/addon-docs',
    '@storybook/addon-a11y',
  ],
  framework: '@storybook/react-vite',
  viteFinal: async (config) => {
    config.plugins = config.plugins ?? []
    config.plugins.push(tailwindcss())

    // Resolve @project/ui → shared/
    const existing = config.resolve?.alias ?? {}
    config.resolve = {
      ...config.resolve,
      alias: Array.isArray(existing)
        ? [...existing, { find: '@project/ui', replacement: path.resolve(root, 'shared') }]
        : { ...existing, '@project/ui': path.resolve(root, 'shared') },
    }

    // Workspace-aware @/* resolver: routes based on which package the file is in
    config.plugins.push({
      name: 'workspace-at-alias',
      resolveId(id: string, importer?: string) {
        if (!id.startsWith('@/') || !importer) return
        const suffix = id.slice(2) // strip @/
        if (importer.includes(`${path.sep}web${path.sep}`)) {
          return path.resolve(root, 'web', suffix)
        }
        if (importer.includes(`${path.sep}admin${path.sep}`)) {
          return path.resolve(root, 'admin', suffix)
        }
      },
    })

    return config
  },
}

export default config
