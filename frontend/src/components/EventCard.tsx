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
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            isRegular ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700'
          }`}>
            {isRegular ? '정기' : '돌발'}
          </span>
          <span className="text-sm font-medium text-gray-800">{event.event_name ?? '할인 행사'}</span>
        </div>
        {event.discount_rate && (
          <span className="text-rose-500 font-bold text-lg shrink-0">-{event.discount_rate}%</span>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
        <span>{flag} {event.platform_name}</span>
        {event.start_date && (
          <span>· {event.start_date}{event.end_date ? ` ~ ${event.end_date}` : ''}</span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {event.original_price && (
          <span className="text-gray-400 line-through text-sm">
            {formatPrice(event.original_price, event.currency)}
          </span>
        )}
        {event.sale_price && (
          <span className="text-gray-800 font-semibold">
            {formatPrice(event.sale_price, event.currency)}
          </span>
        )}
      </div>

      {event.reason && (
        <p className="text-xs text-gray-400 mt-2">{event.reason}</p>
      )}
    </div>
  )
}
