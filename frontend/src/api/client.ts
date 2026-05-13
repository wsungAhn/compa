import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

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
  saving_vs_preferred: number | null
}

export interface ComparisonOut {
  product_name: string
  preferred: PlatformPrice | null
  alternatives: PlatformPrice[]
  cheapest_platform: string | null
  cheapest_saving_pct: number | null
}

export const searchProducts = (q: string) =>
  api.get<Product[]>('/products/search', { params: { q, lang: 'ko' } }).then(r => r.data)

export const getProductEvents = (id: string) =>
  api.get<ProductEvents>(`/products/${id}/events`).then(r => r.data)

export const getComparison = (id: string, preferred: string, platforms?: string) =>
  api.get<ComparisonOut>(`/products/${id}/comparison`, {
    params: { preferred, ...(platforms ? { platforms } : {}) },
  }).then(r => r.data)
