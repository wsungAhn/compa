import { useMemo } from 'react'
import type { SaleEvent } from '../api/client'

interface Props {
  events: SaleEvent[]
}

const COUNTRY_FLAG: Record<string, string> = { KR: '🇰🇷', US: '🇺🇸', JP: '🇯🇵', CN: '🇨🇳' }

function isDateInFuture(dateStr: string | null): boolean {
  if (!dateStr) return false
  const eventDate = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return eventDate > today
}

function calculateDaysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null
  const eventDate = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diffTime = eventDate.getTime() - today.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  return diffDays > 0 ? diffDays : null
}

function formatDateRange(startDate: string | null, endDate: string | null): string {
  if (!startDate) return '날짜 미정'
  const start = new Date(startDate).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
  if (endDate && endDate !== startDate) {
    const end = new Date(endDate).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
    return `${start} ~ ${end}`
  }
  return start
}

export function EventTimeline({ events }: Props) {
  const { sortedEvents, hasAnyWithDates } = useMemo(() => {
    const withDates = events.filter(e => e.start_date !== null)
    const withoutDates = events.filter(e => e.start_date === null)

    const sorted = [
      ...withDates.sort(
        (a, b) => new Date(b.start_date ?? '').getTime() - new Date(a.start_date ?? '').getTime()
      ),
      ...withoutDates,
    ]

    return { sortedEvents: sorted, hasAnyWithDates: withDates.length > 0 }
  }, [events])

  if (!hasAnyWithDates) {
    return null
  }

  return (
    <div className="bg-paper rounded-md border border-ink/10 p-5">
      <h3 className="text-sm font-medium text-ink mb-4">행사 타임라인</h3>

      <div className="space-y-0">
        {sortedEvents.map((event, idx) => {
          const flag = COUNTRY_FLAG[event.platform_country ?? ''] ?? ''
          const isFuture = isDateInFuture(event.start_date)
          const daysUntil = calculateDaysUntil(event.start_date)
          const isRegular = event.event_type === 'regular'
          const isSurprise = event.event_type === 'surprise'

          return (
            <div key={event.id} className="flex gap-4 pb-4">
              {/* Timeline connector */}
              <div className="flex flex-col items-center">
                <div className="w-3 h-3 rounded-full bg-stone flex-shrink-0 mt-1.5" />
                {idx < sortedEvents.length - 1 && (
                  <div className="w-0.5 h-12 bg-linen my-1" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-1">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {isRegular && (
                      <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-md bg-linen text-ink/70">
                        정기
                      </span>
                    )}
                    {isSurprise && (
                      <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-md bg-linen text-ink/70">
                        돌발
                      </span>
                    )}
                    {event.discount_rate && (
                      <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-md bg-linen text-ink/70">
                        -{event.discount_rate}%
                      </span>
                    )}
                    {isFuture && daysUntil !== null && (
                      <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-md bg-linen text-ink/70">
                        D-{daysUntil}
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-sm font-medium text-ink mb-1">
                  {event.event_name ?? '할인 행사'}
                </p>

                <div className="flex items-center gap-2 text-xs text-ink/70 mb-1">
                  <span>{flag} {event.platform_name ?? 'Unknown'}</span>
                  <span>·</span>
                  <span>{formatDateRange(event.start_date, event.end_date)}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
