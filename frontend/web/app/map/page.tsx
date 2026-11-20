import { readDataFile } from '@/lib/data'
import { IncidentMapLoader } from '@/components/incident-map-loader'
import type { Address, StatsData } from '@/lib/types'

export default function MapPage() {
  const addresses = readDataFile<Address[]>('addresses.json')
  const stats = readDataFile<StatsData>('stats.json')

  // The map runs the full width of the window, keeping the page's side padding, instead of
  // stopping at the layout's max-w-7xl. The body clips the scrollbar overflow of w-screen.
  return (
    <div className="relative left-1/2 w-screen -translate-x-1/2 px-5 md:px-8">
      <h1 className="sr-only">Police calls map</h1>
      <IncidentMapLoader addresses={addresses} stats={stats} />
    </div>
  )
}
