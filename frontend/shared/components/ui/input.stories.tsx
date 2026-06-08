import type { Meta, StoryObj } from '@storybook/react-vite'
import { Input } from './input'

const meta: Meta<typeof Input> = {
  component: Input,
  title: 'UI/Input',
}
export default meta

type Story = StoryObj<typeof Input>

export const Default: Story = {
  args: { placeholder: 'Search...' },
}

export const WithValue: Story = {
  args: { defaultValue: 'hello@example.com', type: 'email' },
}

export const Disabled: Story = {
  args: { placeholder: 'Disabled', disabled: true },
}

export const Invalid: Story = {
  args: { placeholder: 'Invalid input', 'aria-invalid': true },
}

export const Password: Story = {
  args: { type: 'password', placeholder: 'Password' },
}
