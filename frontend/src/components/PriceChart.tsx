import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { SaleEvent } from '../api/client'

interface Props {
  events: SaleEvent[]
}

interface ChartDataPoint {
  date: string
  [key: string]: string | number | undefined
}

const COLORS = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

function formatPrice(price: number | null, currency: string | null): string {
  if (!price || !currency) return ''
  const locale = { KRW: 'ko-KR', USD: 'en-US', JPY: 'ja-JP', CNY: 'zh-CN' }[currency] ?? 'ko-KR'
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(price)
}

function getCurrencySymbol(currency: string | null): string {
  const symbols: Record<string, string> = { KRW: '원', USD: '$', JPY: '¥', CNY: '¥' }
  return symbols[currency ?? 'KRW'] ?? '원'
}

function formatYAxisTick(value: unknown): string {
  const num = typeof value === 'number' ? value : 0
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(0)}k`
  }
  return num.toFixed(0)
}

export function PriceChart({ events }: Props) {
  const { chartData, platforms, currency, excluded } = useMemo(() => {
    // Filter events with sale_price and start_date
    const validEvents = events.filter(e => e.sale_price !== null && e.start_date !== null)

    if (validEvents.length < 2) {
      return { chartData: [], platforms: new Set<string>(), currency: null, excluded: [] }
    }

    // Group by currency and count occurrences
    const currencyCount: Record<string, number> = {}
    validEvents.forEach(e => {
      const curr = e.currency ?? 'KRW'
      currencyCount[curr] = (currencyCount[curr] ?? 0) + 1
    })

    // Find the most common currency
    const dominantCurrency = Object.entries(currencyCount).sort(([, a], [, b]) => b - a)[0]?.[0] ?? 'KRW'

    // Filter events by dominant currency
    const filteredEvents = validEvents.filter(e => (e.currency ?? 'KRW') === dominantCurrency)
    const excludedPlatforms = validEvents
      .filter(e => (e.currency ?? 'KRW') !== dominantCurrency)
      .map(e => e.platform_name)
      .filter((v, i, a) => v && a.indexOf(v) === i)

    if (filteredEvents.length < 2) {
      return { chartData: [], platforms: new Set<string>(), currency: dominantCurrency, excluded: excludedPlatforms }
    }

    // Sort by date and build chart data
    const sorted = [...filteredEvents].sort(
      (a, b) => new Date(a.start_date ?? '').getTime() - new Date(b.start_date ?? '').getTime()
    )

    const platforms = new Set<string>()
    const dataMap = new Map<string, ChartDataPoint>()

    sorted.forEach(event => {
      const dateStr = event.start_date ?? ''
      const platformName = event.platform_name ?? 'Unknown'

      if (!dataMap.has(dateStr)) {
        dataMap.set(dateStr, { date: dateStr })
      }

      const dataPoint = dataMap.get(dateStr)
      if (dataPoint) {
        dataPoint[platformName] = event.sale_price ?? undefined
        platforms.add(platformName)
      }
    })

    const chartData = Array.from(dataMap.values())

    return { chartData, platforms, currency: dominantCurrency, excluded: excludedPlatforms }
  }, [events])

  if (chartData.length < 2) {
    return null
  }

  const platformList = Array.from(platforms)

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700">가격 추이</h3>
        {excluded.length > 0 && (
          <p className="text-xs text-gray-400 mt-1">
            {excluded.join(', ')} (단위 제외)
          </p>
        )}
      </div>

      <div className="w-full h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              stroke="#999"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#666' }}
            />
            <YAxis
              stroke="#999"
              style={{ fontSize: '12px' }}
              tickFormatter={formatYAxisTick}
              tick={{ fill: '#666' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #ccc',
                borderRadius: '8px',
                padding: '8px',
              }}
              formatter={(value: unknown) => {
                if (typeof value === 'number') {
                  return formatPrice(value, currency)
                }
                return ''
              }}
              labelStyle={{ color: '#000' }}
            />
            <Legend
              wrapperStyle={{ paddingTop: '16px' }}
              iconType="line"
            />
            {platformList.map((platform, idx) => (
              <Line
                key={platform}
                type="monotone"
                dataKey={platform}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={2}
                dot={{ fill: COLORS[idx % COLORS.length], r: 4 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {currency && (
        <p className="text-xs text-gray-400 mt-3 text-center">
          단위: {getCurrencySymbol(currency)}
        </p>
      )}
    </div>
  )
}
