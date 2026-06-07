import { Card, CardContent, CardHeader, CardTitle } from '@project/ui/components/ui/card'

interface Props {
  total: number
  generatedAt: string
}

export function StatsCards({ total, generatedAt }: Props) {
  const updated = generatedAt ? generatedAt.slice(0, 10) : '—'
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 mb-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Total Incidents
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{total.toLocaleString()}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Data Updated
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-lg font-medium">{updated}</p>
        </CardContent>
      </Card>
    </div>
  )
}
