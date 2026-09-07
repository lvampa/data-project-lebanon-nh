import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Input } from '../input'

export default {
  title: 'Forms/Input',
} satisfies StoryDefault

type InputProps = ComponentProps<typeof Input>

export const Default: Story<InputProps> = (props) => <Input {...props} />
Default.args = { placeholder: 'Search...' }

export const WithValue: Story<InputProps> = (props) => <Input {...props} />
WithValue.args = { defaultValue: 'hello@example.com', type: 'email' }

export const Disabled: Story<InputProps> = (props) => <Input {...props} />
Disabled.args = { placeholder: 'Disabled', disabled: true }

export const Invalid: Story<InputProps> = (props) => <Input {...props} />
Invalid.args = { placeholder: 'Invalid input', 'aria-invalid': true }

export const Password: Story<InputProps> = (props) => <Input {...props} />
Password.args = { type: 'password', placeholder: 'Password' }
