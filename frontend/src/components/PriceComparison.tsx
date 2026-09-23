import type { ComparisonOut } from '../api/client'

interface Props {
  data: ComparisonOut
}

const CURRENCY_SYMBOL: Record<string, string> = {
  KRW: '₩', USD: '$', JPY: '¥', CNY: '¥'
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
        <div className="bg-paper rounded-md border border-moss p-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-ink">{preferred.platform_name} 현재가</span>
            {preferred.discount_rate && (
              <span className="text-xs bg-moss text-paper font-medium px-2 py-0.5 rounded-md tabular-nums">
                -{preferred.discount_rate}%
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-medium text-ink tabular-nums">
              {formatPrice(preferred.sale_price, preferred.currency) ?? '가격 정보 없음'}
            </span>
            {preferred.original_price && (
              <span className="text-sm text-ink/70 line-through">
                {formatPrice(preferred.original_price, preferred.currency)}
              </span>
            )}
          </div>
          {preferred.event_name && (
            <p className="text-xs text-ink/70 mt-1">{preferred.event_name}</p>
          )}
        </div>
      )}

      {cheapest_platform && cheapest_saving_pct && cheapest_saving_pct > 0 && (
        <div className="bg-linen border border-ink/10 rounded-md px-4 py-2 flex items-center gap-2">
          <span className="text-sm text-ink font-medium">
            {cheapest_platform}에서 약 {cheapest_saving_pct}% 더 저렴해요
          </span>
        </div>
      )}

      {alternatives.length > 0 && (
        <div>
          <p className="text-xs text-ink/70 font-medium mb-2 px-1">다른 사이트 비교</p>
          <div className="space-y-2">
            {alternatives.map(alt => (
              <div
                key={alt.platform_name}
                className={`bg-paper rounded-md border border-ink/10 p-3 flex items-center justify-between ${
                  (alt.saving_vs_preferred ?? 0) > 0
                    ? 'border-moss'
                    : 'border-ink/10'
                }`}
              >
                <div>
                  <span className="text-sm font-medium text-ink">{alt.platform_name}</span>
                  {alt.event_name && (
                    <span className="ml-2 text-xs text-ink/70">{alt.event_name}</span>
                  )}
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-2">
                    {(alt.saving_vs_preferred ?? 0) > 0 && (
                      <span className="text-xs text-moss font-medium tabular-nums">
                        -{CURRENCY_SYMBOL[alt.currency ?? 'KRW']}{alt.saving_vs_preferred?.toLocaleString()} 저렴
                      </span>
                    )}
                    <div className="flex flex-col items-end">
                      <span className={`text-sm font-medium tabular-nums ${(alt.saving_vs_preferred ?? 0) > 0 ? 'text-moss' : 'text-ink'}`}>
                        {formatPrice(alt.sale_price, alt.currency) ?? '—'}
                      </span>
                      {alt.converted_price && alt.currency && alt.currency !== (preferred?.currency ?? 'KRW') && (
                        <span className="text-xs text-ink/70">
                          ≈ {formatPrice(alt.converted_price, preferred?.currency ?? 'KRW')}
                        </span>
                      )}
                    </div>
                  </div>
                  {alt.discount_rate && (
                    <span className="text-xs text-ink/70 tabular-nums">-{alt.discount_rate}%</span>
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
