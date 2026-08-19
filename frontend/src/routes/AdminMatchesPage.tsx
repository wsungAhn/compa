import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  approveProductMatch,
  listProductMatches,
  rejectProductMatch,
  setAdminSecretHeader,
  type ProductMatchCandidate,
} from '../api/client'
import { useAdminSecret } from '../hooks/useAdminSecret'
import './AdminMatchesPage.css'

type RowStatus = 'pending' | 'approved' | 'rejected' | 'conflict'
type Action = 'approved' | 'rejected'

interface ReviewRow extends ProductMatchCandidate {
  reviewStatus: RowStatus
  processing: boolean
}

function getErrorStatus(error: unknown): number | null {
  if (typeof error !== 'object' || error === null) return null
  const maybeResponse = 'response' in error ? error.response : null
  if (typeof maybeResponse !== 'object' || maybeResponse === null) return null
  const maybeStatus = 'status' in maybeResponse ? maybeResponse.status : null
  return typeof maybeStatus === 'number' ? maybeStatus : null
}

function toRows(candidates: ProductMatchCandidate[]): ReviewRow[] {
  return candidates.map(candidate => ({
    ...candidate,
    reviewStatus: 'pending',
    processing: false,
  }))
}

function shortId(id: string): string {
  return id.slice(0, 8)
}

function displayName(name: string | null): string {
  return name?.trim() || '이름 없음'
}

function displayBrand(brand: string | null): string {
  return brand?.trim() || '브랜드 미상'
}

export function AdminMatchesPage() {
  const { adminSecret, setAdminSecret } = useAdminSecret()
  const [secretInput, setSecretInput] = useState('')
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(false)
  const [actingId, setActingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resolvedSession, setResolvedSession] = useState(0)
  const [approvedSession, setApprovedSession] = useState(0)
  const removeTimers = useRef<number[]>([])

  useEffect(() => {
    setAdminSecretHeader(adminSecret)
    return () => setAdminSecretHeader(null)
  }, [adminSecret])

  useEffect(() => {
    const timers = removeTimers.current
    return () => {
      timers.forEach(window.clearTimeout)
    }
  }, [])

  const loadMatches = useCallback(async () => {
    if (!adminSecret) return
    setLoading(true)
    setError(null)
    try {
      const candidates = await listProductMatches('pending')
      setRows(toRows(candidates))
      setSelected(0)
    } catch (err) {
      const status = getErrorStatus(err)
      setRows([])
      if (status === 404) {
        setError('시크릿을 확인해주세요')
      } else {
        setError('매칭 목록을 불러오지 못했습니다')
      }
    } finally {
      setLoading(false)
    }
  }, [adminSecret])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadMatches()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadMatches])

  const pendingCount = useMemo(
    () => rows.filter(row => row.reviewStatus === 'pending').length,
    [rows]
  )
  const approveRate =
    resolvedSession === 0 ? '0%' : `${Math.round((approvedSession / resolvedSession) * 100)}%`

  const removeRow = useCallback((id: string) => {
    setRows(current => {
      const removedIndex = current.findIndex(row => row.id === id)
      const next = current.filter(row => row.id !== id)
      setSelected(previous => {
        if (next.length === 0) return 0
        if (removedIndex === -1) return Math.min(previous, next.length - 1)
        if (removedIndex < previous) return Math.max(0, previous - 1)
        return Math.min(previous, next.length - 1)
      })
      return next
    })
  }, [])

  const scheduleRemove = useCallback(
    (id: string) => {
      const timer = window.setTimeout(() => removeRow(id), 1100)
      removeTimers.current.push(timer)
    },
    [removeRow]
  )

  const act = useCallback(
    async (id: string | null, action: Action) => {
      if (!id || actingId) return
      const row = rows.find(candidate => candidate.id === id)
      if (!row || row.reviewStatus !== 'pending') return

      setActingId(id)
      setError(null)
      setRows(current =>
        current.map(candidate =>
          candidate.id === id ? { ...candidate, processing: true } : candidate
        )
      )

      try {
        if (action === 'approved') {
          await approveProductMatch(id)
        } else {
          await rejectProductMatch(id)
        }

        setRows(current =>
          current.map(candidate =>
            candidate.id === id
              ? { ...candidate, reviewStatus: action, processing: false }
              : candidate
          )
        )
        setResolvedSession(count => count + 1)
        if (action === 'approved') {
          setApprovedSession(count => count + 1)
        }
        scheduleRemove(id)
      } catch (err) {
        const status = getErrorStatus(err)
        if (status === 409) {
          setRows(current =>
            current.map(candidate =>
              candidate.id === id
                ? { ...candidate, reviewStatus: 'conflict', processing: false }
                : candidate
            )
          )
        } else if (status === 404) {
          setRows(current =>
            current.map(candidate =>
              candidate.id === id ? { ...candidate, processing: false } : candidate
            )
          )
          setError('시크릿을 확인해주세요')
        } else {
          setRows(current =>
            current.map(candidate =>
              candidate.id === id ? { ...candidate, processing: false } : candidate
            )
          )
          setError('매칭 처리에 실패했습니다')
        }
      } finally {
        setActingId(null)
      }
    },
    [actingId, rows, scheduleRemove]
  )

  const selectedId = rows[selected]?.reviewStatus === 'pending' ? rows[selected].id : null

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target
      if (
        target instanceof HTMLElement &&
        /INPUT|TEXTAREA/.test(target.tagName)
      ) {
        return
      }
      if (!rows.some(row => row.reviewStatus === 'pending')) return

      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const delta = event.key === 'ArrowDown' ? 1 : -1
        setSelected(current => Math.min(Math.max(current + delta, 0), rows.length - 1))
      } else if (event.key === 'a' || event.key === 'A') {
        void act(selectedId, 'approved')
      } else if (event.key === 'r' || event.key === 'R') {
        void act(selectedId, 'rejected')
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [act, rows, selectedId])

  async function applySecret() {
    const trimmed = secretInput.trim()
    if (!trimmed) return
    setAdminSecret(trimmed)
    setSecretInput('')
  }

  function clearSecret() {
    setAdminSecret(null)
    setRows([])
    setSelected(0)
    setError(null)
  }

  return (
    <div className="admin-match-page">
      <header className="admin-match-topbar">
        <div className="admin-match-brand">
          <span className="admin-match-logo">compa</span>
          <span className="admin-match-eyebrow">Admin</span>
        </div>
        <div className="admin-match-divider" />
        <div className="admin-match-title">
          <span className="admin-match-title-main">매칭 검토</span>
          <span className="admin-match-title-sub">Match Review</span>
        </div>
        <div className="admin-match-stats">
          <div className="admin-match-stat">
            <span className="admin-match-stat-label">대기</span>
            <span className="admin-match-stat-value accent">{pendingCount}</span>
          </div>
          <div className="admin-match-stat">
            <span className="admin-match-stat-label">오늘 처리</span>
            <span className="admin-match-stat-value">{resolvedSession}</span>
          </div>
          <div className="admin-match-stat">
            <span className="admin-match-stat-label">승인율</span>
            <span className="admin-match-stat-value">{approveRate}</span>
          </div>
        </div>
      </header>

      <main className="admin-match-main">
        <div className="admin-match-queue-header">
          <div>
            <h1 className="admin-match-heading">검토 대기열</h1>
            <p className="admin-match-copy">
              자동 매칭 시스템이 동일 상품 후보로 판별한 리스팅 쌍입니다. 각 항목을 승인 또는 거절하세요.
            </p>
          </div>
          {adminSecret ? (
            <div className="admin-match-hints">
              <span className="admin-match-hint"><kbd className="admin-match-kbd">↑↓</kbd> 이동</span>
              <span className="admin-match-hint"><kbd className="admin-match-kbd">A</kbd> 승인</span>
              <span className="admin-match-hint"><kbd className="admin-match-kbd">R</kbd> 거절</span>
            </div>
          ) : null}
        </div>

        {!adminSecret ? (
          <section className="admin-match-panel admin-match-secret">
            <div className="admin-match-panel-title">관리자 시크릿이 필요합니다</div>
            <div className="admin-match-panel-copy">
              매칭 검토 큐를 불러오려면 기존 관리자 시크릿을 입력하세요.
            </div>
            <div className="admin-match-secret-form">
              <input
                className="admin-match-secret-input"
                type="password"
                value={secretInput}
                onChange={event => setSecretInput(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') void applySecret()
                }}
                placeholder="관리자 시크릿"
              />
              <button
                className="admin-match-button primary"
                type="button"
                disabled={!secretInput.trim()}
                onClick={() => void applySecret()}
              >
                적용
              </button>
            </div>
          </section>
        ) : null}

        {adminSecret && loading ? (
          <section className="admin-match-panel admin-match-loading">
            <div className="admin-match-panel-title">대기열을 불러오는 중</div>
            <div className="admin-match-panel-copy">매칭 후보 목록을 확인하고 있습니다.</div>
          </section>
        ) : null}

        {adminSecret && !loading && error ? (
          <section className="admin-match-panel admin-match-secret">
            <div className="admin-match-panel-title">목록을 표시할 수 없습니다</div>
            <div className="admin-match-error">{error}</div>
            <div className="admin-match-button-row">
              <button className="admin-match-button primary" type="button" onClick={() => void loadMatches()}>
                다시 시도
              </button>
              <button className="admin-match-button secondary" type="button" onClick={clearSecret}>
                시크릿 변경
              </button>
            </div>
          </section>
        ) : null}

        {adminSecret && !loading && !error && rows.length > 0 ? (
          <>
            <div className="admin-match-col-header">
              <div>기존 표기</div>
              <div />
              <div>매칭 후보</div>
              <div className="admin-match-col-right">신뢰도</div>
              <div className="admin-match-col-right">작업</div>
            </div>
            <div className="admin-match-queue">
              {rows.map((row, index) => {
                const pct = Math.round(row.score * 100)
                const low = row.score < 0.8
                const isSelected = index === selected && row.reviewStatus === 'pending'
                const rowClasses = [
                  'admin-match-row',
                  row.reviewStatus,
                  isSelected ? 'selected' : '',
                ].filter(Boolean).join(' ')

                return (
                  <div
                    key={row.id}
                    role="button"
                    tabIndex={row.reviewStatus === 'pending' ? 0 : -1}
                    className={rowClasses}
                    onClick={() => {
                      if (row.reviewStatus === 'pending') setSelected(index)
                    }}
                    onKeyDown={event => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        if (row.reviewStatus === 'pending') setSelected(index)
                      }
                    }}
                  >
                    <div className="admin-match-product">
                      <div className="admin-match-brand-line">{displayBrand(row.brand)}</div>
                      <div className="admin-match-product-name">{displayName(row.orphan_name)}</div>
                      <div className="admin-match-product-id">orphan · {shortId(row.orphan_product_id)}</div>
                    </div>
                    <div className="admin-match-glyph">⇌</div>
                    <div className="admin-match-product">
                      <div className="admin-match-brand-line">{displayBrand(row.brand)}</div>
                      <div className="admin-match-product-name">{displayName(row.canonical_name)}</div>
                      <div className="admin-match-product-id">canonical · {shortId(row.canonical_product_id)}</div>
                    </div>
                    <div className="admin-match-confidence">
                      <span className={`admin-match-score${low ? ' low' : ''}`}>{pct}%</span>
                      <div className="admin-match-score-track">
                        <div
                          className={`admin-match-score-bar${low ? ' low' : ''}`}
                          style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
                        />
                      </div>
                    </div>
                    <div className="admin-match-actions">
                      {row.reviewStatus === 'pending' ? (
                        <div className="admin-match-button-row">
                          <button
                            className="admin-match-button primary"
                            type="button"
                            disabled={row.processing || actingId !== null}
                            onClick={event => {
                              event.stopPropagation()
                              void act(row.id, 'approved')
                            }}
                          >
                            {row.processing ? '처리 중' : '승인'}
                          </button>
                          <button
                            className="admin-match-button secondary"
                            type="button"
                            disabled={row.processing || actingId !== null}
                            onClick={event => {
                              event.stopPropagation()
                              void act(row.id, 'rejected')
                            }}
                          >
                            거절
                          </button>
                        </div>
                      ) : null}
                      {row.reviewStatus === 'approved' || row.reviewStatus === 'rejected' ? (
                        <span className={`admin-match-resolved-label ${row.reviewStatus}`}>
                          {row.reviewStatus === 'approved' ? '승인됨' : '거절됨'}
                        </span>
                      ) : null}
                      {row.reviewStatus === 'conflict' ? (
                        <div className="admin-match-conflict-box">
                          <div className="admin-match-conflict-text">
                            <div className="admin-match-conflict-title">이미 처리된 항목</div>
                            <div className="admin-match-conflict-copy">다른 운영자가 방금 해결했습니다</div>
                          </div>
                          <button
                            className="admin-match-button confirm"
                            type="button"
                            onClick={event => {
                              event.stopPropagation()
                              removeRow(row.id)
                            }}
                          >
                            확인
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="admin-match-footer">
              <span>신뢰도 90% 이상은 자동 승인 후보입니다</span>
              <span>행을 클릭해 선택 · 단축키로 빠르게 처리</span>
            </div>
          </>
        ) : null}

        {adminSecret && !loading && !error && rows.length === 0 ? (
          <section className="admin-match-panel admin-match-empty">
            <div className="admin-match-empty-count">0</div>
            <div className="admin-match-panel-title">검토할 매칭이 없습니다</div>
            <div className="admin-match-panel-copy">
              대기열이 비었습니다. 새 매칭 후보는 자동 매칭 배치가 완료되는 대로 이곳에 표시됩니다.
            </div>
            <button className="admin-match-button secondary" type="button" onClick={() => void loadMatches()}>
              대기열 새로고침
            </button>
          </section>
        ) : null}
      </main>
    </div>
  )
}
