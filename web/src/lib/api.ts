import type { DemoResponse, UploadResponse } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function analyzeDemo(scenario: string): Promise<DemoResponse> {
  const res = await fetch(`${API_BASE}/demo/analyze`, {
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
  const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Upload analysis failed')
  }
  return res.json()
}

export async function analyzePaste(text: string): Promise<UploadResponse> {
  return analyzeUpload([new File([text], 'pasted.log', { type: 'text/plain' })])
}
