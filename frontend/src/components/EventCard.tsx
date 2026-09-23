import type { SaleEvent } from '../api/client'

interface Props {
  event: SaleEvent
}

const COUNTRY_FLAG: Record<string, string> = { KR: '🇰🇷', US: '🇺🇸', JP: '🇯🇵', CN: '🇨🇳' }

function formatPrice(price: number | null, currency: string | null) {
  if (!price || !currency) return null
  const locale = { KRW: 'ko-KR', USD: 'en-US', JPY: 'ja-JP', CNY: 'zh-CN' }[currency] ?? 'ko-KR'
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(price)
}

export function EventCard({ event }: Props) {
  const isRegular = event.event_type === 'regular'
  const flag = COUNTRY_FLAG[event.platform_country ?? ''] ?? ''

  return (
    <div className="bg-paper rounded-md border border-ink/10 p-4 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-linen text-ink/70">
            {isRegular ? '정기' : '돌발'}
          </span>
          <span className="text-sm font-medium text-ink">{event.event_name ?? '할인 행사'}</span>
        </div>
        {event.discount_rate && (
          <span className="text-ink font-medium text-lg tabular-nums shrink-0">-{event.discount_rate}%</span>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-ink/70 mb-2">
        <span>{flag} {event.platform_name}</span>
        {event.start_date && (
          <span>· {event.start_date}{event.end_date ? ` ~ ${event.end_date}` : ''}</span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {event.original_price && (
          <span className="text-ink/70 line-through text-sm">
            {formatPrice(event.original_price, event.currency)}
          </span>
        )}
        {event.sale_price && (
          <span className="text-ink font-medium tabular-nums">
            {formatPrice(event.sale_price, event.currency)}
          </span>
        )}
      </div>

      {event.reason && (
        <p className="text-xs text-ink/70 mt-2">{event.reason}</p>
      )}
    </div>
  )
}
