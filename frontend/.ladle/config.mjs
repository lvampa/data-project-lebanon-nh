/** @type {import('@ladle/react').UserConfig} */
export default {
  stories: '{shared,web,admin}/components/**/*.stories.{ts,tsx}',
  viteConfig: '.ladle/vite.config.ts',
  addons: {
    a11y: { enabled: true },
  },
}
