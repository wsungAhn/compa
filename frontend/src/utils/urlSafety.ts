export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null

  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    return url
  } catch {
    return null
  }
}
