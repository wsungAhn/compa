import type { Recommendation } from '../api/client'

interface Props {
  recommendation: Recommendation
}

const VERDICT_CONFIG = {
  wait: { emoji: '⏳', label: '기다리세요', bg: 'bg-amber-50', border: 'border-amber-400', text: 'text-amber-700' },
  buy_now: { emoji: '🛒', label: '지금 사세요', bg: 'bg-rose-50', border: 'border-rose-400', text: 'text-rose-700' },
  good_deal: { emoji: '✅', label: '나쁘지 않아요', bg: 'bg-emerald-50', border: 'border-emerald-400', text: 'text-emerald-700' },
}

export function WaitBuyWidget({ recommendation }: Props) {
  const cfg = VERDICT_CONFIG[recommendation.verdict]

  return (
    <div className={`rounded-2xl border-2 ${cfg.border} ${cfg.bg} p-5`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-3xl">{cfg.emoji}</span>
        <span className={`text-xl font-bold ${cfg.text}`}>{cfg.label}</span>
      </div>

      <p className="text-gray-600 text-sm mb-4">{recommendation.reason}</p>

      <div className="flex gap-4 flex-wrap">
        {recommendation.days_until_next !== null && (
          <div className="bg-white rounded-xl px-4 py-2 text-center shadow-sm">
            <div className="text-2xl font-bold text-gray-800">D-{recommendation.days_until_next}</div>
            <div className="text-xs text-gray-500">{recommendation.next_event_name}</div>
          </div>
        )}
        {recommendation.expected_discount !== null && (
          <div className="bg-white rounded-xl px-4 py-2 text-center shadow-sm">
            <div className="text-2xl font-bold text-rose-500">-{recommendation.expected_discount}%</div>
            <div className="text-xs text-gray-500">예상 할인율</div>
          </div>
        )}
      </div>
    </div>
  )
}
