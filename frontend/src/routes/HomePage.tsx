import { useState, useEffect } from 'react'
import { SearchBar } from '../components/SearchBar'
import { WaitBuyWidget } from '../components/WaitBuyWidget'
import { PriceComparison } from '../components/PriceComparison'
import { SiteEventsGrid } from '../components/SiteEventsGrid'
import { EventTimeline } from '../components/EventTimeline'
import { PriceChart } from '../components/PriceChart'
import { SiteManager } from '../components/SiteManager'
import { SiteFooter } from '../components/SiteFooter'
import { FeedbackButton } from '../components/FeedbackButton'
import { PremiumBanner } from '../components/PremiumBanner'
import { useSitePrefs } from '../hooks/useSitePrefs'
import { usePremium } from '../hooks/usePremium'
import { getProductEvents, getComparison, setPremiumHeader } from '../api/client'
import type { Product, ProductEvents, ComparisonOut, SaleEvent } from '../api/client'

export function HomePage() {
  const [selected, setSelected] = useState<Product | null>(null)
  const [data, setData] = useState<ProductEvents | null>(null)
  const [comparison, setComparison] = useState<ComparisonOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [collecting, setCollecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { sites, preferred, moveUp, moveDown, addSite, removeSite, availableToAdd } = useSitePrefs()
  const { premiumKey, setPremiumKey } = usePremium()

  // Initialize premium header on app start and when key changes
  useEffect(() => {
    setPremiumHeader(premiumKey)
  }, [premiumKey])

  async function fetchProductData(product: Product) {
    setError(null)
    setLoading(true)
    try {
      const [eventsResult, comparisonResult] = await Promise.allSettled([
        getProductEvents(product.id),
        preferred
          ? getComparison(product.id, preferred.name, sites.map(s => s.name).join(','))
          : Promise.reject(new Error('no preferred')),
      ])
      if (eventsResult.status === 'fulfilled') setData(eventsResult.value)
      if (comparisonResult.status === 'fulfilled') setComparison(comparisonResult.value)
      if (eventsResult.status === 'rejected') setError('데이터를 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSelect(product: Product) {
    setSelected(product)
    setData(null)
    setComparison(null)
    await fetchProductData(product)
  }

  async function handlePremiumActivated() {
    if (selected) {
      await fetchProductData(selected)
    }
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-paper border-b border-ink/10 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-3">
          <h1 className="text-lg font-medium tracking-wide text-ink">compa</h1>
          <span className="text-xs text-ink/70">지금 살지 · 기다릴지</span>
          <div className="ml-auto flex items-center gap-2">
            <FeedbackButton />
            <SiteManager
              sites={sites}
              availableToAdd={availableToAdd}
              onMoveUp={moveUp}
              onMoveDown={moveDown}
              onAdd={addSite}
              onRemove={removeSite}
            />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-col items-center gap-2">
        <p className="text-ink/70 text-sm">화장품 이름을 검색하면 할인 이력을 분석해드려요</p>
          <div className="w-full flex items-center gap-2">
            <div className="flex-1">
              <SearchBar onSelect={handleSelect} onCollecting={setCollecting} />
            </div>
          </div>
          {preferred && (
            <p className="text-xs text-ink/70">
              기준 사이트: <span className="font-medium text-ink">{preferred.flag} {preferred.name}</span>
            </p>
          )}
        </div>

        {collecting && (
          <div className="bg-linen border border-ink/10 rounded-md p-4 flex items-center gap-2">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink/20 border-t-moss" />
            <span className="text-sm text-ink/70">백그라운드 수집 중... 잠시 후 결과가 업데이트됩니다</span>
          </div>
        )}

        {loading && (
          <div className="space-y-3 animate-pulse">
            <div className="h-28 bg-linen rounded-md" />
            <div className="h-20 bg-linen rounded-md" />
            <div className="h-20 bg-linen rounded-md" />
          </div>
        )}

        {error && (
          <div className="bg-linen border border-clay rounded-md p-4 text-ink text-sm">{error}</div>
        )}

        {(data || comparison) && !loading && (
          <div className="space-y-5">
            {data && (
              <div>
                <h2 className="text-xl font-display font-normal text-ink">{data.product.name_kr ?? data.product.name_en}</h2>
                {data.product.brand && <p className="text-sm text-ink/70">{data.product.brand}</p>}
              </div>
            )}

            {data && !data.premium && (
              <PremiumBanner
                premium={false}
                onActivated={handlePremiumActivated}
                onKeyChange={setPremiumKey}
              />
            )}

            {data && data.premium && (
              <div className='flex justify-end'>
                <PremiumBanner
                  premium={true}
                  onActivated={handlePremiumActivated}
                  onKeyChange={setPremiumKey}
                />
              </div>
            )}

            {comparison && <PriceComparison data={comparison} />}

            {data && <WaitBuyWidget recommendation={data.recommendation} />}

            {data && <PriceChart events={data.events} />}

            {data && <EventTimeline events={data.events} />}

            {data && data.events.length > 0 && (
              <SiteEventsGrid
                eventsByPlatform={data.events.reduce<Record<string, SaleEvent[]>>((acc, e) => {
                  const platform = e.platform_name ?? 'Unknown'
                  ;(acc[platform] ??= []).push(e)
                  return acc
                }, {})}
              />
            )}
            {data && data.events.length === 0 && (
              <div className="text-center py-8">
                <p className="text-ink/70 text-sm">아직 수집된 할인 이력이 없어요</p>
              </div>
            )}

          </div>
        )}

        {!selected && !loading && (
          <div className="space-y-8">
          <div className="text-center py-16 text-ink/70">
              <p className="text-sm">검색어를 입력해 할인 정보를 확인하세요</p>
            </div>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  )
}
