import type { ComparisonOut } from '../api/client'

interface Props {
  data: ComparisonOut
}

const CURRENCY_SYMBOL: Record<string, string> = {
  KRW: 'W', USD: '$', JPY: 'Y', CNY: 'Y'
}

function formatPrice(price: number | null, currency: string | null) {
  if (!price || !currency) return null
  const locale = { KRW: 'ko-KR', USD: 'en-US', JPY: 'ja-JP', CNY: 'zh-CN' }[currency] ?? 'ko-KR'
  return new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 0 }).format(price)
}

export function PriceComparison({ data }: Props) {
  const { preferred, alternatives, cheapest_platform, cheapest_saving_pct } = data

  return (
    <div className="space-y-3">
      {preferred && (
        <div className="bg-white rounded-2xl border-2 border-rose-200 p-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-semibold text-gray-700">{preferred.platform_name} 현재가</span>
            {preferred.discount_rate && (
              <span className="text-xs bg-rose-100 text-rose-600 font-bold px-2 py-0.5 rounded-full">
                -{preferred.discount_rate}%
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-900">
              {formatPrice(preferred.sale_price, preferred.currency) ?? '가격 정보 없음'}
            </span>
            {preferred.original_price && (
              <span className="text-sm text-gray-400 line-through">
                {formatPrice(preferred.original_price, preferred.currency)}
              </span>
            )}
          </div>
          {preferred.event_name && (
            <p className="text-xs text-rose-500 mt-1">{preferred.event_name}</p>
          )}
        </div>
      )}

      {cheapest_platform && cheapest_saving_pct && cheapest_saving_pct > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2 flex items-center gap-2">
          <span className="text-lg">💡</span>
          <span className="text-sm text-emerald-700 font-medium">
            {cheapest_platform}에서 약 {cheapest_saving_pct}% 더 저렴해요
          </span>
        </div>
      )}

      {alternatives.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 font-semibold mb-2 px-1">다른 사이트 비교</p>
          <div className="space-y-2">
            {alternatives.map(alt => (
              <div
                key={alt.platform_name}
                className={`bg-white rounded-xl border p-3 flex items-center justify-between ${
                  (alt.saving_vs_preferred ?? 0) > 0
                    ? 'border-emerald-200'
                    : 'border-gray-100'
                }`}
              >
                <div>
                  <span className="text-sm font-medium text-gray-700">{alt.platform_name}</span>
                  {alt.event_name && (
                    <span className="ml-2 text-xs text-gray-400">{alt.event_name}</span>
                  )}
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-2">
                    {(alt.saving_vs_preferred ?? 0) > 0 && (
                      <span className="text-xs text-emerald-600 font-semibold">
                        -{CURRENCY_SYMBOL[alt.currency ?? 'KRW']}{alt.saving_vs_preferred?.toLocaleString()} 저렴
                      </span>
                    )}
                    <span className={`text-sm font-bold ${(alt.saving_vs_preferred ?? 0) > 0 ? 'text-emerald-700' : 'text-gray-700'}`}>
                      {formatPrice(alt.sale_price, alt.currency) ?? '—'}
                    </span>
                  </div>
                  {alt.discount_rate && (
                    <span className="text-xs text-rose-400">-{alt.discount_rate}%</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
