import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export function setPremiumHeader(key: string | null) {
  if (key) {
    api.defaults.headers.common['X-Premium-Key'] = key
  } else {
    delete api.defaults.headers.common['X-Premium-Key']
  }
}

export function setAdminSecretHeader(key: string | null) {
  if (key) {
    api.defaults.headers.common['X-Admin-Secret'] = key
  } else {
    delete api.defaults.headers.common['X-Admin-Secret']
  }
}

export interface Product {
  id: string
  name_kr: string | null
  name_en: string | null
  name_jp: string | null
  name_cn: string | null
  brand: string | null
  category: string | null
}

export interface SaleEvent {
  id: string
  event_name: string | null
  event_type: string | null
  start_date: string | null
  end_date: string | null
  platform_name: string | null
  platform_country: string | null
  original_price: number | null
  sale_price: number | null
  discount_rate: number | null
  currency: string | null
  reason: string | null
  source_url: string | null
  confidence: number | null
}

export interface Recommendation {
  verdict: 'wait' | 'buy_now' | 'good_deal'
  reason: string
  next_event_name: string | null
  days_until_next: number | null
  expected_discount: number | null
}

export interface ProductEvents {
  product: Product
  events: SaleEvent[]
  recommendation: Recommendation
  premium: boolean
}

export interface PlatformPrice {
  platform_name: string
  platform_country: string
  sale_price: number | null
  original_price: number | null
  discount_rate: number | null
  currency: string | null
  event_name: string | null
  source_url: string | null
  converted_price: number | null
  saving_vs_preferred: number | null
}

export interface ComparisonOut {
  product_name: string
  preferred: PlatformPrice | null
  alternatives: PlatformPrice[]
  cheapest_platform: string | null
  cheapest_saving_pct: number | null
}

export interface SearchResponse {
  products: Product[]
  job_id: string | null
  collecting: boolean
}

export interface JobStatus {
  task_id: string
  status: 'pending' | 'started' | 'success' | 'failure'
  ready: boolean
}

export interface ProductMatchCandidate {
  id: string
  orphan_product_id: string
  orphan_name: string | null
  canonical_product_id: string
  canonical_name: string | null
  brand: string | null
  score: number
  status: string
  created_at: string
}

export interface DealSignal {
  id: string
  brand: string | null
  title: string
  discount_pct: number | null
  price: string | null
  source: string
  source_url: string | null
  posted_at: string | null
}

export const searchProducts = (q: string, collect = false) =>
  api.get<SearchResponse>('/products/search', { params: { q, lang: 'ko', collect } }).then(r => r.data)

export const getJobStatus = (taskId: string) =>
  api.get<JobStatus>(`/jobs/${taskId}`).then(r => r.data)

export const getProductEvents = (id: string) =>
  api.get<ProductEvents>(`/products/${id}/events`).then(r => r.data)

export const getComparison = (id: string, preferred: string, platforms?: string) =>
  api.get<ComparisonOut>(`/products/${id}/comparison`, {
    params: { preferred, ...(platforms ? { platforms } : {}) },
  }).then(r => r.data)

export const listProductMatches = (status: 'pending' = 'pending') =>
  api.get<ProductMatchCandidate[]>('/admin/product-matches', { params: { status } }).then(r => r.data)

export const approveProductMatch = (id: string): Promise<void> =>
  api.post(`/admin/product-matches/${id}/approve`).then(() => undefined)

export const rejectProductMatch = (id: string): Promise<void> =>
  api.post(`/admin/product-matches/${id}/reject`).then(() => undefined)

export const listDeals = (): Promise<DealSignal[]> =>
  api.get<DealSignal[]>('/deals').then(r => r.data)

const BASE_URL = ''

export async function postFeedback(
  message: string,
  contact?: string,
  page?: string
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, contact, page }),
  })
  if (!res.ok) throw new Error(`feedback failed: ${res.status}`)
}
