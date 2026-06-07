'use client'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@project/ui/components/ui/chart'
import { Bar, BarChart, CartesianGrid, XAxis } from 'recharts'

interface Props {
  data: { day: string; count: number }[]
}

const chartConfig = {
  count: { label: 'Incidents', color: 'hsl(var(--chart-2))' },
}

export function WeekdayChart({ data }: Props) {
  return (
    <ChartContainer config={chartConfig} className="h-48 w-full">
      <BarChart data={data}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="day" />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="count" fill="var(--color-count)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}
