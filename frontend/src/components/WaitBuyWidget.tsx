import type { Recommendation } from '../api/client'

interface Props {
  recommendation: Recommendation
}

const VERDICT_CONFIG = {
  wait: { label: '기다리세요', bg: 'bg-linen', border: 'border-ink/10', text: 'text-ink' },
  buy_now: { label: '지금 사세요', bg: 'bg-linen', border: 'border-moss', text: 'text-moss' },
  good_deal: { label: '나쁘지 않아요', bg: 'bg-linen', border: 'border-ink/10', text: 'text-ink' },
}

export function WaitBuyWidget({ recommendation }: Props) {
  const cfg = VERDICT_CONFIG[recommendation.verdict]

  return (
    <div className={`rounded-md border ${cfg.border} ${cfg.bg} p-5`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`font-display text-2xl font-normal ${cfg.text}`}><span className="mr-2">●</span>{cfg.label}</span>
      </div>

      <p className="text-ink/70 text-sm mb-4">{recommendation.reason}</p>

      <div className="flex gap-4 flex-wrap">
        {recommendation.days_until_next !== null && (
          <div className="bg-paper border border-ink/10 rounded-md px-4 py-2 text-center">
            <div className="text-2xl font-medium text-ink tabular-nums">D-{recommendation.days_until_next}</div>
            <div className="text-xs text-ink/70">{recommendation.next_event_name}</div>
          </div>
        )}
        {recommendation.expected_discount !== null && (
          <div className="bg-paper border border-ink/10 rounded-md px-4 py-2 text-center">
            <div className="text-lg font-medium text-ink tabular-nums">-{recommendation.expected_discount}%</div>
            <div className="text-xs text-ink/70">예상 할인율</div>
          </div>
        )}
      </div>
    </div>
  )
}
