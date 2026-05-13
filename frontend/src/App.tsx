import { useState } from 'react'
import { SearchBar } from './components/SearchBar'
import { WaitBuyWidget } from './components/WaitBuyWidget'
import { EventCard } from './components/EventCard'
import { PriceComparison } from './components/PriceComparison'
import { SiteManager } from './components/SiteManager'
import { useSitePrefs } from './hooks/useSitePrefs'
import { getProductEvents, getComparison } from './api/client'
import type { Product, ProductEvents, ComparisonOut } from './api/client'

export default function App() {
  const [selected, setSelected] = useState<Product | null>(null)
  const [data, setData] = useState<ProductEvents | null>(null)
  const [comparison, setComparison] = useState<ComparisonOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { sites, preferred, moveUp, moveDown, addSite, removeSite, availableToAdd } = useSitePrefs()

  async function handleSelect(product: Product) {
    setSelected(product)
    setData(null)
    setComparison(null)
    setError(null)
    setLoading(true)
    try {
      const eventsResult = await getProductEvents(product.id).then(
        v => ({ ok: true as const, value: v }),
        () => ({ ok: false as const })
      )
      const comparisonResult = preferred
        ? await getComparison(product.id, preferred.name, sites.map(s => s.name).join(',')).then(
            v => ({ ok: true as const, value: v }),
            () => ({ ok: false as const })
          )
        : { ok: false as const }

      if (eventsResult.ok) setData(eventsResult.value)
      else setError('데이터를 불러오지 못했습니다.')
      if (comparisonResult.ok) setComparison(comparisonResult.value)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className='min-h-screen bg-gray-50'>
      <header className='bg-white border-b border-gray-100 sticky top-0 z-20 shadow-sm'>
        <div className='max-w-2xl mx-auto px-4 py-4 flex items-center gap-3'>
          <span className='text-2xl'>💄</span>
          <h1 className='text-lg font-bold text-gray-800'>COMPA</h1>
          <span className='text-xs text-gray-400'>지금 살지 · 기다릴지</span>
          <div className='ml-auto'>
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

      <main className='max-w-2xl mx-auto px-4 py-8 space-y-6'>
        <div className='flex flex-col items-center gap-2'>
          <p className='text-gray-500 text-sm'>화장품 이름을 검색하면 할인 이력을 분석해드려요</p>
          <div className='w-full flex items-center gap-2'>
            <div className='flex-1'>
              <SearchBar onSelect={handleSelect} />
            </div>
          </div>
          {preferred && (
            <p className='text-xs text-gray-400'>
              기준 사이트: <span className='font-semibold text-gray-600'>{preferred.flag} {preferred.name}</span>
            </p>
          )}
        </div>

        {loading && (
          <div className='space-y-3 animate-pulse'>
            <div className='h-28 bg-gray-200 rounded-2xl' />
            <div className='h-20 bg-gray-200 rounded-xl' />
            <div className='h-20 bg-gray-200 rounded-xl' />
          </div>
        )}

        {error && (
          <div className='bg-red-50 border border-red-200 rounded-xl p-4 text-red-600 text-sm'>{error}</div>
        )}

        {(data || comparison) && !loading && (
          <div className='space-y-5'>
            {data && (
              <div>
                <h2 className='text-xl font-bold text-gray-900'>{data.product.name_kr ?? data.product.name_en}</h2>
                {data.product.brand && <p className='text-sm text-gray-500'>{data.product.brand}</p>}
              </div>
            )}

            {comparison && <PriceComparison data={comparison} />}

            {data && <WaitBuyWidget recommendation={data.recommendation} />}

            {data && (
              <div>
                <h3 className='text-sm font-semibold text-gray-600 mb-3'>
                  할인 이력 {data.events.length > 0 ? `(${data.events.length}건)` : ''}
                </h3>
                {data.events.length === 0 ? (
                  <p className='text-gray-400 text-sm text-center py-8'>아직 수집된 할인 이력이 없어요</p>
                ) : (
                  <div className='space-y-3'>
                    {data.events.map(e => <EventCard key={e.id} event={e} />)}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {!selected && !loading && (
          <div className='text-center py-16 text-gray-300'>
            <div className='text-6xl mb-4'>🔍</div>
            <p className='text-sm'>검색어를 입력해 할인 정보를 확인하세요</p>
          </div>
        )}
      </main>
    </div>
  )
}
