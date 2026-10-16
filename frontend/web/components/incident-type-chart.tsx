'use client'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@project/ui/components/ui/chart'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

interface Props {
  data: { name: string; count: number }[]
}

const chartConfig = {
  count: { label: 'Incidents', color: 'hsl(var(--chart-1))' },
}

export function IncidentTypeChart({ data }: Props) {
  return (
    <ChartContainer config={chartConfig} className="h-80 w-full">
      <BarChart data={data} layout="vertical" margin={{ left: 120 }}>
        <CartesianGrid horizontal={false} />
        <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 11 }} />
        <XAxis type="number" />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="count" fill="var(--color-count)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}
