'use client'

import { useState } from 'react'
import type { AnalysisResult } from '@/lib/types'

interface Props {
  analysis: AnalysisResult | null
  remediationCommand: string | null
  loading: boolean
  error: string | null
}

export default function AnalysisResults({ analysis, remediationCommand, loading, error }: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (!remediationCommand) return
    navigator.clipboard.writeText(remediationCommand)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const confidenceColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-500/20 text-green-400 border border-green-500/30'
    if (score >= 0.6) return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
    return 'bg-red-500/20 text-red-400 border border-red-500/30'
  }

  if (loading) {
    return (
      <div className="mt-8 flex flex-col items-center gap-4 py-12">
        <div className="w-10 h-10 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm">Analyzing logs with AI...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-8 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
        <p className="text-red-400 text-sm font-medium">⚠ Analysis Error</p>
        <p className="text-red-300 text-sm mt-1">{error}</p>
      </div>
    )
  }

  if (!analysis) return null

  return (
    <div className="mt-8 rounded-xl border border-green-500/30 bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-green-400 text-lg">🧠</span>
          <h3 className="text-white font-semibold">Root Cause Analysis</h3>
        </div>
        <span className={`text-xs font-mono px-2 py-1 rounded-full ${confidenceColor(analysis.confidence_score)}`}>
          {Math.round(analysis.confidence_score * 100)}% confidence
        </span>
      </div>

      <div className="p-6 space-y-5">
        {/* Summary */}
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Summary</p>
          <p className="text-white text-sm leading-relaxed">{analysis.summary}</p>
        </div>

        {/* Root Cause */}
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Root Cause</p>
          <p className="text-gray-300 text-sm leading-relaxed">{analysis.root_cause_description}</p>
        </div>

        {/* Affected Components */}
        {analysis.affected_components?.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Affected Components</p>
            <div className="flex flex-wrap gap-2">
              {analysis.affected_components.map((c) => (
                <span key={c} className="text-xs px-2 py-1 rounded bg-gray-800 text-gray-300 border border-gray-700 font-mono">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Remediation */}
        {remediationCommand && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Remediation Command</p>
            <div className="relative rounded-lg bg-gray-950 border border-gray-800 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800">
                <span className="text-xs text-gray-500 font-mono">bash</span>
                <button
                  onClick={handleCopy}
                  className="text-xs text-gray-400 hover:text-green-400 transition-colors"
                >
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <pre className="px-4 py-3 text-sm text-green-400 font-mono overflow-x-auto whitespace-pre-wrap break-all">
                {remediationCommand}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
