import type { SaleEvent } from '../api/client'
import { SiteTimeline } from './SiteTimeline'

interface Props {
  eventsByPlatform: Record<string, SaleEvent[]>
}

/**
 * 진행 중인 이벤트 또는 최근 이벤트의 가격 가져오기
 */
function getCurrentSalePrice(events: SaleEvent[]): number | null {
  const today = new Date().toISOString().slice(0, 10)
  const ongoing = events.find(
    e => e.start_date && e.end_date && e.start_date <= today && e.end_date >= today
  )
  return (ongoing ?? events[0])?.sale_price ?? null
}

export function SiteEventsGrid({ eventsByPlatform }: Props) {
  const platforms = Object.keys(eventsByPlatform).sort()

  if (platforms.length === 0) {
    return null
  }

  // 통화별로 최저가 플랫폼 찾기
  const cheapestByCurrency: Record<string, string> = {}

  platforms.forEach(platformName => {
    const events = eventsByPlatform[platformName]
    const currency = events[0]?.currency
    const price = getCurrentSalePrice(events)

    if (currency && price != null) {
      if (!cheapestByCurrency[currency]) {
        cheapestByCurrency[currency] = platformName
      } else {
        const currentCheapest = cheapestByCurrency[currency]
        const currentCheapestPrice = getCurrentSalePrice(eventsByPlatform[currentCheapest])
        if (currentCheapestPrice != null && price < currentCheapestPrice) {
          cheapestByCurrency[currency] = platformName
        }
      }
    }
  })

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-600">사이트별 할인 이력</h3>
      <div className="platform-grid">
        {platforms.map(platformName => {
          const events = eventsByPlatform[platformName]
          const currency = events[0]?.currency
          const isCheapest = currency ? cheapestByCurrency[currency] === platformName : false

          return (
            <SiteTimeline
              key={platformName}
              platformName={platformName}
              events={events}
              isCheapest={isCheapest}
            />
          )
        })}
      </div>
    </div>
  )
}
