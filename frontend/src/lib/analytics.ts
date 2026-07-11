declare global {
  interface Window {
    sa_event?: (event: string, data?: Record<string, unknown>) => void
  }
}

export function track(event: string, data?: Record<string, unknown>) {
  if (typeof window !== 'undefined' && window.sa_event) {
    window.sa_event(event, data)
  }
}
