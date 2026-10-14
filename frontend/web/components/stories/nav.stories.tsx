import type { Story, StoryDefault } from '@ladle/react'
import { NavBar } from '../nav'

export default {
  title: 'Layout/Nav',
} satisfies StoryDefault

export const Home: Story = () => <NavBar pathname="/" />

export const SectionActive: Story = () => <NavBar pathname="/incidents/26-14680" />

export const AboutActive: Story = () => <NavBar pathname="/about" />

export const PhoneWidth: Story = () => (
  <div style={{ width: 390, border: '1px dashed #ccc' }}>
    <NavBar pathname="/incidents" />
  </div>
)
