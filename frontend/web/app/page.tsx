import { readDataFile } from '@/lib/data'
import { formatTypeData, formatWeekdayData } from '@/lib/chart-utils'
import { StatsCards } from '@/components/stats-cards'
import { IncidentTypeChart } from '@/components/incident-type-chart'
import { WeekdayChart } from '@/components/weekday-chart'
import { Card, CardContent, CardHeader, CardTitle } from '@project/ui/components/ui/card'
import type { StatsData } from '@/lib/types'

export default function DashboardPage() {
  const stats = readDataFile<StatsData>('stats.json')
  const typeData = formatTypeData(stats.by_type, 15)
  const weekdayData = formatWeekdayData(stats.by_weekday)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Lebanon NH Police Incidents</h1>
      <StatsCards total={stats.total} generatedAt={stats.generated_at} />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Incident Types</CardTitle>
          </CardHeader>
          <CardContent>
            <IncidentTypeChart data={typeData} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Day of Week</CardTitle>
          </CardHeader>
          <CardContent>
            <WeekdayChart data={weekdayData} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
