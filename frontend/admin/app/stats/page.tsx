import { fetchStatsByType, fetchStatsByHour, fetchStatsByWeekday } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@project/ui/components/ui/card'

export default async function StatsPage() {
  const [byType, byHour, byWeekday] = await Promise.all([
    fetchStatsByType(),
    fetchStatsByHour(),
    fetchStatsByWeekday(),
  ])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Stats</h1>
      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top Incident Types</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <tbody>
                {byType.map((row) => (
                  <tr key={row.incident_type} className="border-b last:border-0">
                    <td className="py-1">{row.incident_type}</td>
                    <td className="py-1 text-right tabular-nums">{row.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Hour of Day</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <tbody>
                {byHour.map((row) => (
                  <tr key={row.hour} className="border-b last:border-0">
                    <td className="py-1">{row.hour}:00</td>
                    <td className="py-1 text-right tabular-nums">{row.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Day of Week</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <tbody>
                {byWeekday.map((row) => (
                  <tr key={row.day} className="border-b last:border-0">
                    <td className="py-1">{row.day}</td>
                    <td className="py-1 text-right tabular-nums">{row.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
