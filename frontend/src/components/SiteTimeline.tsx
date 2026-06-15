import type { SaleEvent } from '../api/client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface SiteTimelineProps {
  platformName: string
  events: SaleEvent[]
  isCheapest?: boolean
}

interface ChartPoint {
  date: string
  discount: number
  saleEvent?: SaleEvent
}

const COUNTRY_FLAG: Record<string, string> = { KR: '🇰🇷', US: '🇺🇸', JP: '🇯🇵', CN: '🇨🇳' }

/**
 * 통화별 숫자 포맷 (정수 표시)
 */
function formatPrice(price: number | null, currency: string | null): string {
  if (price == null || currency == null) return '-'
  try {
    const fmt = new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    })
    return fmt.format(price)
  } catch {
    return `${price} ${currency}`
  }
}

/**
 * 오늘 날짜가 이벤트 기간 내인지 확인
 */
function isEventOngoing(event: SaleEvent): boolean {
  if (!event.start_date || !event.end_date) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const startDate = new Date(event.start_date)
  const endDate = new Date(event.end_date)
  return today >= startDate && today <= endDate
}

/**
 * 현재가 정보 (진행 중인 이벤트 또는 최근 이벤트)
 */
function getCurrentPrice(events: SaleEvent[]): { price: number | null; label: string; event: SaleEvent | null } {
  const ongoingEvent = events.find(e => isEventOngoing(e))
  if (ongoingEvent) {
    return { price: ongoingEvent.sale_price, label: '진행 중', event: ongoingEvent }
  }
  const recent = events[0]
  if (recent?.sale_price != null) {
    return { price: recent.sale_price, label: '최근 수집', event: recent }
  }
  return { price: null, label: '', event: null }
}

/**
 * 차트 데이터 생성 (3년 범위의 날짜별 할인율)
 */
function buildChartData(events: SaleEvent[]): ChartPoint[] {
  const points: ChartPoint[] = []

  // 3년 전 시작점 (0%)
  const start = new Date()
  start.setFullYear(start.getFullYear() - 3)
  points.push({ date: start.toISOString().slice(0, 10), discount: 0 })

  // start_date가 있는 이벤트만, 날짜순 정렬
  const sorted = [...events]
    .filter(e => e.start_date)
    .sort((a, b) => a.start_date!.localeCompare(b.start_date!))

  for (const event of sorted) {
    const rate = Math.round(event.discount_rate ?? 0)

    // 이벤트 시작 포인트
    points.push({ date: event.start_date!, discount: rate, saleEvent: event })

    // 이벤트 종료 다음날 → 0으로 복귀
    if (event.end_date) {
      const dayAfter = new Date(event.end_date)
      dayAfter.setDate(dayAfter.getDate() + 1)
      points.push({ date: dayAfter.toISOString().slice(0, 10), discount: 0 })
    }
  }

  // 오늘 (마지막 포인트, 0%)
  points.push({ date: new Date().toISOString().slice(0, 10), discount: 0 })

  // 날짜순 정렬, 같은 날짜 내 discount 큰 것 우선
  return points.sort((a, b) =>
    a.date !== b.date
      ? a.date.localeCompare(b.date)
      : b.discount - a.discount
  )
}

/**
 * X축 날짜 포맷 (예: "24.3" = 2024년 3월)
 */
function formatDateTick(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getFullYear()).slice(2)}.${d.getMonth() + 1}`
}

/**
 * 커스텀 툴팁 (이벤트 정보 표시)
 */
function CustomTooltip(props: unknown) {
  const { active, payload } = props as { active?: boolean; payload?: Array<{ payload: ChartPoint }> }
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  if (!point.saleEvent || point.discount === 0) return null

  const e = point.saleEvent
  const currency = e.currency ?? null

  return (
    <div className="bg-gray-800 text-white text-[11px] rounded-lg px-3 py-2 shadow-xl pointer-events-none">
      <p className="font-semibold mb-0.5">{e.event_name ?? '-'}</p>
      <p>
        {formatPrice(e.sale_price, currency)}
        <span className="text-blue-300 ml-1">-{point.discount}%</span>
      </p>
      <p className="text-gray-400 text-[10px] mt-0.5">
        {e.start_date} ~ {e.end_date ?? '?'}
      </p>
    </div>
  )
}

export function SiteTimeline({ platformName, events, isCheapest }: SiteTimelineProps) {
  const countryCode = events[0]?.platform_country ?? ''
  const flag = COUNTRY_FLAG[countryCode] ?? ''
  const currency = events[0]?.currency ?? null

  // start_date가 있는 이벤트만 필터링 (타임라인용)
  const timelineEvents = events.filter(e => e.start_date != null)

  const { price: currentPrice, label: currentLabel, event: currentEvent } = getCurrentPrice(events)
  const currentUrl = currentEvent?.source_url ?? null
  const isCurrentOngoing = currentEvent ? isEventOngoing(currentEvent) : false

  // 차트 데이터 생성
  const chartData = buildChartData(timelineEvents)
  const maxDiscount = Math.max(...chartData.map(p => p.discount), 10)

  const gradientId = `grad-${platformName.replace(/\s+/g, '-')}`

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2">
          <span className="text-lg">{flag}</span>
          <span className="font-semibold text-gray-800 text-sm flex-1">{platformName}</span>
          {currentPrice != null && (
            <div className="flex items-center gap-2">
              <div className="text-right">
                <div className="text-xs text-gray-500">{currentLabel}</div>
                <div className={`font-semibold text-sm ${isCurrentOngoing ? 'text-rose-600' : 'text-gray-700'}`}>
                  {formatPrice(currentPrice, currency)}
                </div>
              </div>
              {isCheapest && (
                <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1 py-0.5 rounded whitespace-nowrap">
                  최저가
                </span>
              )}
            </div>
          )}
          {currentUrl && (
            <a
              href={currentUrl}
              target="_blank"
              rel="noopener"
              className="ml-2 text-blue-500 hover:text-blue-700 text-lg"
              title="상품 페이지 이동"
            >
              →
            </a>
          )}
        </div>
      </div>

      {/* 타임라인 (AreaChart) */}
      <div className="px-4 pb-4 flex-1">
        {timelineEvents.length === 0 ? (
          <p className="text-gray-400 text-xs text-center py-8">수집된 이력 없음</p>
        ) : (
          <ResponsiveContainer width="100%" height={100}>
            <AreaChart
              data={chartData}
              margin={{ top: 8, right: 4, left: -30, bottom: 0 }}
            >
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tickFormatter={formatDateTick}
                tick={{ fontSize: 9, fill: '#9ca3af' }}
                interval="preserveStartEnd"
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, maxDiscount + 5]}
                hide
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="stepAfter"
                dataKey="discount"
                stroke="#3b82f6"
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, fill: '#3b82f6' }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
