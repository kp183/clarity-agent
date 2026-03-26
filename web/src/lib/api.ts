import type { DemoResponse, UploadResponse } from './types'

// v2 - force fresh build
const API_BASE = 'https://clarity-agent.onrender.com'

async function fetchWithRetry(url: string, options: RequestInit, retries = 2): Promise<Response> {
  for (let i = 0; i <= retries; i++) {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 45000)
      const res = await fetch(url, { ...options, signal: controller.signal })
      clearTimeout(timeout)
      return res
    } catch (err) {
      if (i === retries) throw err
      await new Promise(resolve => setTimeout(resolve, 2000))
    }
  }
  throw new Error('Max retries exceeded')
}

export async function analyzeDemo(scenario: string): Promise<DemoResponse> {
  const res = await fetchWithRetry(`${API_BASE}/demo/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Demo analysis failed')
  }
  return res.json()
}

export async function analyzeUpload(files: File[]): Promise<UploadResponse> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const res = await fetchWithRetry(`${API_BASE}/analyze`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Upload analysis failed')
  }
  return res.json()
}

export async function analyzePaste(text: string): Promise<UploadResponse> {
  return analyzeUpload([new File([text], 'pasted.log', { type: 'text/plain' })])
}
