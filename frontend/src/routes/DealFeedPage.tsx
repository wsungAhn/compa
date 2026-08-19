// User-facing deal signal feed page.
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listDeals, type DealSignal } from '../api/client'
import { formatRelativeTime, getHoursOld } from './DealFeedPage.helpers'
import './DealFeedPage.css'

const FADE_START_HOURS = 24

interface DealRow extends DealSignal {
  hoursOld: number | null
}

function sourceLabel(source: string): string {
  if (source === 'reddit') return 'Reddit'
  if (source === 'slickdeals') return 'Slickdeals'
  return source
}

function discountLabel(discountPct: number | null): string | null {
  if (discountPct === null) return null
  return `-${Math.round(discountPct)}%`
}

function priceLabel(price: string | null): string | null {
  if (!price) return null
  return `$${price}`
}

export function DealFeedPage() {
  const [deals, setDeals] = useState<DealSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadDeals() {
      setLoading(true)
      setError(null)
      try {
        const rows = await listDeals()
        if (active) setDeals(rows)
      } catch {
        if (active) {
          setDeals([])
          setError('딜 피드를 불러오지 못했습니다')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadDeals()
    return () => {
      active = false
    }
  }, [])

  const rows = useMemo<DealRow[]>(
    () => deals.map(deal => ({ ...deal, hoursOld: getHoursOld(deal.posted_at) })),
    [deals]
  )

  return (
    <div className="deal-feed-page">
      <header className="deal-feed-topbar">
        <Link className="deal-feed-logo" to="/">compa</Link>
        <nav className="deal-feed-nav" aria-label="주요 화면">
          <Link to="/">가격 비교</Link>
          <Link to="/admin/coverage">가격 히스토리</Link>
          <Link className="active" to="/deals">딜 피드</Link>
        </nav>
        <div className="deal-feed-live">
          <span aria-hidden="true" />
          <span className="deal-feed-live-full">실시간 수집 중</span>
          <span className="deal-feed-live-short">실시간</span>
        </div>
      </header>

      <main className="deal-feed-main">
        <div className="deal-feed-heading-row">
          <div>
            <h1>지금 이야기되는 딜</h1>
            <p className="deal-feed-copy">
              Reddit과 Slickdeals 커뮤니티에서 발견된 화장품 딜입니다. 48시간 동안만 표시됩니다.
            </p>
          </div>
          <div className="deal-feed-live desktop-only">
            <span aria-hidden="true" />
            실시간 수집 중
          </div>
        </div>

        {loading ? (
          <section className="deal-feed-panel deal-feed-loading">
            <div className="deal-feed-panel-title">딜을 불러오는 중</div>
            <div className="deal-feed-panel-copy">커뮤니티 원본 신호를 확인하고 있습니다.</div>
          </section>
        ) : null}

        {!loading && error ? (
          <section className="deal-feed-panel deal-feed-empty">
            <div className="deal-feed-dot muted" />
            <div className="deal-feed-panel-title">목록을 표시할 수 없습니다</div>
            <div className="deal-feed-panel-copy">{error}</div>
          </section>
        ) : null}

        {!loading && !error && rows.length === 0 ? (
          <section className="deal-feed-panel deal-feed-empty">
            <div className="deal-feed-dot muted" />
            <div className="deal-feed-panel-title">지금은 조용하네요</div>
            <div className="deal-feed-panel-copy">
              현재 진행 중인 딜이 없습니다. 커뮤니티에서 새 딜이 발견되면 바로 이곳에 올라옵니다.
            </div>
            <div className="deal-feed-empty-link">
              대신 <Link to="/admin/coverage">가격 히스토리</Link>에서 역대 최저가를 확인해 보세요
            </div>
          </section>
        ) : null}

        {!loading && !error && rows.length > 0 ? (
          <>
            <div className="deal-feed-list">
              {rows.map(row => {
                const stale = row.hoursOld !== null && row.hoursOld >= FADE_START_HOURS
                const discount = discountLabel(row.discount_pct)
                const price = priceLabel(row.price)
                const time = formatRelativeTime(row.posted_at)
                const content = (
                  <>
                    <div className="deal-feed-item-main">
                      <div className="deal-feed-meta-line">
                        {row.brand ? <span className="deal-feed-brand">{row.brand}</span> : null}
                        {time ? <span className="deal-feed-time">{time}</span> : null}
                      </div>
                      <div className="deal-feed-title">{row.title}</div>
                      <div className="deal-feed-source-line">
                        <span className="deal-feed-source">{sourceLabel(row.source)}</span>
                        {row.source_url ? <span>원문 보기 ↗</span> : null}
                      </div>
                    </div>
                    <div className="deal-feed-signal">
                      {discount ? <div className="deal-feed-discount">{discount}</div> : null}
                      {price ? <div className="deal-feed-price">{price}</div> : null}
                    </div>
                  </>
                )

                if (!row.source_url) {
                  return (
                    <div key={row.id} className={`deal-feed-item${stale ? ' stale' : ''}`}>
                      {content}
                    </div>
                  )
                }

                return (
                  <a
                    key={row.id}
                    className={`deal-feed-item${stale ? ' stale' : ''}`}
                    href={row.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {content}
                  </a>
                )
              })}
            </div>
            <p className="deal-feed-footnote">
              딜은 게시 48시간 후 자동으로 사라집니다 · 확인된 딜은 가격 히스토리에 반영됩니다
            </p>
          </>
        ) : null}
      </main>
    </div>
  )
}
