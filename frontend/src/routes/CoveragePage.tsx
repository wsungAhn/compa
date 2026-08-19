// Admin matching coverage dashboard page.
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getCoverage,
  setAdminSecretHeader,
  type Coverage,
  type CoverageOrphan,
} from '../api/client'
import { useAdminSecret } from '../hooks/useAdminSecret'
import { clampPct, formatCount, getBatchWindow } from './CoveragePage.helpers'
import './CoveragePage.css'

function getErrorStatus(error: unknown): number | null {
  if (typeof error !== 'object' || error === null) return null
  const maybeResponse = 'response' in error ? error.response : null
  if (typeof maybeResponse !== 'object' || maybeResponse === null) return null
  const maybeStatus = 'status' in maybeResponse ? maybeResponse.status : null
  return typeof maybeStatus === 'number' ? maybeStatus : null
}

function displayValue(value: string | null): string {
  return value?.trim() || '정보 없음'
}

function ageClass(orphan: CoverageOrphan): string {
  return orphan.unmatched_days >= 7 ? 'coverage-age overdue' : 'coverage-age'
}

export function CoveragePage() {
  const { adminSecret, setAdminSecret } = useAdminSecret()
  const [secretInput, setSecretInput] = useState('')
  const [coverage, setCoverage] = useState<Coverage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const batchWindow = useMemo(() => getBatchWindow(), [])

  useEffect(() => {
    setAdminSecretHeader(adminSecret)
    return () => setAdminSecretHeader(null)
  }, [adminSecret])

  const loadCoverage = useCallback(async () => {
    if (!adminSecret) return
    setLoading(true)
    setError(null)
    try {
      setCoverage(await getCoverage())
    } catch (err) {
      setCoverage(null)
      setError(getErrorStatus(err) === 404 ? '시크릿을 확인해주세요' : '커버리지를 불러오지 못했습니다')
    } finally {
      setLoading(false)
    }
  }, [adminSecret])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCoverage()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadCoverage])

  async function applySecret() {
    const trimmed = secretInput.trim()
    if (!trimmed) return
    setAdminSecret(trimmed)
    setSecretInput('')
  }

  function clearSecret() {
    setAdminSecret(null)
    setCoverage(null)
    setError(null)
  }

  const coveragePct = coverage?.coverage_pct ?? 0
  const barWidth = `${clampPct(coveragePct)}%`

  return (
    <div className="coverage-page">
      <header className="coverage-topbar">
        <div className="coverage-brand">
          <span className="coverage-logo">compa</span>
          <span className="coverage-eyebrow">Admin</span>
        </div>
        <div className="coverage-divider" />
        <div className="coverage-title">
          <span className="coverage-title-main">매칭 커버리지</span>
          <span className="coverage-title-sub">Matching Coverage</span>
        </div>
        <div className="coverage-schedule">
          <span aria-hidden="true" />
          마지막 배치 {batchWindow.lastBatch} · 다음 배치 {batchWindow.nextBatch} · 스케줄 기준
        </div>
      </header>

      <main className="coverage-main">
        {!adminSecret ? (
          <section className="coverage-panel coverage-secret">
            <div className="coverage-panel-title">관리자 시크릿이 필요합니다</div>
            <div className="coverage-panel-copy">
              매칭 커버리지 지표를 보려면 기존 관리자 시크릿을 입력하세요.
            </div>
            <div className="coverage-secret-form">
              <input
                className="coverage-secret-input"
                type="password"
                value={secretInput}
                onChange={event => setSecretInput(event.target.value)}
                onKeyDown={event => {
                  if (event.key === 'Enter') void applySecret()
                }}
                placeholder="관리자 시크릿"
              />
              <button
                className="coverage-button primary"
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
          <section className="coverage-panel coverage-loading">
            <div className="coverage-panel-title">커버리지를 불러오는 중</div>
            <div className="coverage-panel-copy">상품 카탈로그의 현재 매칭 상태를 계산하고 있습니다.</div>
          </section>
        ) : null}

        {adminSecret && !loading && error ? (
          <section className="coverage-panel coverage-secret">
            <div className="coverage-panel-title">커버리지를 표시할 수 없습니다</div>
            <div className="coverage-error">{error}</div>
            <div className="coverage-button-row">
              <button className="coverage-button primary" type="button" onClick={() => void loadCoverage()}>
                다시 시도
              </button>
              <button className="coverage-button secondary" type="button" onClick={clearSecret}>
                시크릿 변경
              </button>
            </div>
          </section>
        ) : null}

        {adminSecret && !loading && !error && coverage ? (
          <>
            <section className="coverage-metric">
              <div className="coverage-scope">교차 매칭 커버리지 (JP -&gt; EN 백필)</div>
              <div className="coverage-metric-row">
                <div className="coverage-primary">
                  <span className="coverage-pct">{coveragePct.toFixed(1)}%</span>
                  <span className="coverage-counts">
                    {formatCount(coverage.matched_count)} / {formatCount(coverage.total_count)} 매칭됨
                  </span>
                </div>
                <div className="coverage-secondary">
                  <div>
                    <div className="coverage-stat-label">미매칭 (orphan)</div>
                    <div className="coverage-stat-value">{formatCount(coverage.orphan_count)}</div>
                  </div>
                </div>
              </div>
              <div className="coverage-bar-track">
                <div className="coverage-bar-fill" style={{ width: barWidth }} />
              </div>
              <div className="coverage-bar-caption">
                <span>매칭됨 <span className="coverage-square">■</span></span>
                <span>배치 주기 6시간 · 커버리지는 현재 DB 카운트 기준</span>
              </div>
            </section>

            <section className="coverage-orphans">
              <div className="coverage-orphan-heading">
                <div>
                  <h1>미매칭 상품 샘플</h1>
                  <p>오래된 JP orphan 최대 {coverage.orphans.length}건</p>
                </div>
              </div>
              <div className="coverage-table-wrap">
                <table className="coverage-table">
                  <thead>
                    <tr>
                      <th>브랜드</th>
                      <th>상품명</th>
                      <th>소스 국가</th>
                      <th className="coverage-right">미매칭 기간</th>
                    </tr>
                  </thead>
                  <tbody>
                    {coverage.orphans.map((orphan, index) => (
                      <tr key={`${orphan.source_country}-${orphan.name ?? index}`}>
                        <td className="coverage-brand-cell">{displayValue(orphan.brand)}</td>
                        <td className="coverage-name-cell">{displayValue(orphan.name)}</td>
                        <td className="coverage-country-cell">{orphan.source_country}</td>
                        <td className={ageClass(orphan)}>{orphan.unmatched_days}일</td>
                      </tr>
                    ))}
                    {coverage.orphans.length === 0 ? (
                      <tr>
                        <td className="coverage-empty-row" colSpan={4}>현재 표시할 orphan 샘플이 없습니다</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
              <p className="coverage-footnote">
                7일 이상 미매칭 상태인 상품은 진하게 표시됩니다. 미매칭 기간은 상품 생성 시각 기준입니다.
              </p>
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}
