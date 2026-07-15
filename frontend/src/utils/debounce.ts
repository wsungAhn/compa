export interface DebouncedFunction<TArgs extends unknown[]> {
  (...args: TArgs): void
  cancel: () => void
}

export function debounce<TArgs extends unknown[]>(
  fn: (...args: TArgs) => void,
  delayMs: number
): DebouncedFunction<TArgs> {
  let timer: ReturnType<typeof setTimeout> | null = null

  const debounced = (...args: TArgs) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, delayMs)
  }

  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  return debounced
}
