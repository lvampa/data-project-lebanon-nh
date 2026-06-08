import type { Meta, StoryObj } from '@storybook/react-vite'
import { IncidentMarker, type MarkerState, type MarkerCategory } from './IncidentMarker'
import { ClusterBubble } from './ClusterBubble'

const meta: Meta = {
  title: 'Map/Markers',
  parameters: { layout: 'padded' },
}
export default meta

const MAP_BG: React.CSSProperties = {
  background: 'radial-gradient(circle at 12px 12px, rgba(0,0,0,0.12) 1px, transparent 1.5px), oklch(0.970 0 0)',
  backgroundSize: '24px 24px',
  padding: 24,
  borderRadius: 8,
}

const STATES: MarkerState[] = ['default', 'hover', 'selected', 'muted']
const CATEGORIES: MarkerCategory[] = [1, 2, 3, 4, 5]
const CAT_LABELS = ['Fire', 'Medical', 'Traffic', 'Utility', 'Police']

export const AllStatesAndCategories: StoryObj = {
  render: () => (
    <div style={MAP_BG}>
      <div style={{ display: 'grid', gridTemplateColumns: `80px repeat(5, 1fr)`, gap: 8, alignItems: 'center' }}>
        <div />
        {CAT_LABELS.map((l) => (
          <div key={l} style={{ fontSize: 10, color: 'oklch(0.556 0 0)', textTransform: 'uppercase', letterSpacing: '0.06em', textAlign: 'center' }}>{l}</div>
        ))}
        {STATES.map((s) => (
          <>
            <div key={s} style={{ fontSize: 10, color: 'oklch(0.556 0 0)', textTransform: 'uppercase', letterSpacing: '0.06em', textAlign: 'right', paddingRight: 8 }}>{s}</div>
            {CATEGORIES.map((c) => (
              <div key={c} style={{ display: 'grid', placeItems: 'center', padding: '10px 0' }}>
                <IncidentMarker category={c} state={s} />
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  ),
}

export const SingleMarker: StoryObj<typeof IncidentMarker> = {
  render: (args) => (
    <div style={{ ...MAP_BG, display: 'inline-flex' }}>
      <IncidentMarker {...args} />
    </div>
  ),
  args: { category: 1, state: 'default' },
  argTypes: {
    category: { control: 'select', options: [1, 2, 3, 4, 5] },
    state: { control: 'select', options: STATES },
  },
}

export const Clusters: StoryObj = {
  render: () => (
    <div style={{ ...MAP_BG, display: 'flex', gap: 32, alignItems: 'center' }}>
      {([
        { count: 4, size: 'sm' as const },
        { count: 42, size: 'md' as const },
        { count: 318, size: 'lg' as const },
      ]).map(({ count, size }) => (
        <div key={size} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <ClusterBubble count={count} size={size} />
          <span style={{ fontSize: 10, color: 'oklch(0.556 0 0)' }}>{size} · {count}</span>
        </div>
      ))}
    </div>
  ),
}
