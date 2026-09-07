import type { ComponentProps } from 'react'
import type { Story, StoryDefault } from '@ladle/react'
import { Checkbox } from '../checkbox'

export default {
  title: 'Forms/Checkbox',
} satisfies StoryDefault

type CheckboxProps = ComponentProps<typeof Checkbox>

export const Default: Story<CheckboxProps> = (props) => <Checkbox {...props} />
Default.args = { label: 'Show officer names' }

export const Checked: Story<CheckboxProps> = (props) => <Checkbox {...props} />
Checked.args = { label: 'Verified records only', defaultChecked: true }

export const Indeterminate: Story<CheckboxProps> = (props) => <Checkbox {...props} />
Indeterminate.args = { label: 'Select all', indeterminate: true }

export const WithDescription: Story<CheckboxProps> = (props) => <Checkbox {...props} />
WithDescription.args = {
  label: 'Include historical data',
  description: 'Load incidents older than 90 days',
  defaultChecked: false,
}

export const Disabled: Story<CheckboxProps> = (props) => <Checkbox {...props} />
Disabled.args = { label: 'Admin only', disabled: true, defaultChecked: true }
