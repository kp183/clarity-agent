'use client'

import { useState, useRef, useCallback } from 'react'
import AnalysisResults from '@/components/AnalysisResults'
import { analyzeDemo, analyzeUpload, analyzePaste } from '@/lib/api'
import type { AnalysisResult, DemoResponse, UploadResponse } from '@/lib/types'

const SCENARIOS = [
  {
    id: 'db_pool',
    icon: '🗄️',
    title: 'Database Pool Exhaustion',
    description: 'Traffic spike overwhelms DB connection pool, cascading into service outage.',
    events: 80,
    services: ['auth-service', 'database', 'api-gateway'],
    severity: 'high',
  },
  {
    id: 'memory_leak',
    icon: '🧠',
    title: 'Memory Leak Detection',
    description: 'Gradual heap growth leads to OOM killer and CrashLoopBackOff.',
    events: 80,
    services: ['payment-service', 'cache'],
    severity: 'critical',
  },
  {
    id: 'deployment_bug',
    icon: '🚀',
    title: 'Deployment Regression',
    description: 'New release introduces NullPointerException, triggering auto-rollback.',
    events: 60,
    services: ['user-service', 'api-gateway'],
    severity: 'high',
  },
]

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
}

export default function Home() {
  // Demo section state
  const [activeScenario, setActiveScenario] = useState<string | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)
  const [demoAnalysis, setDemoAnalysis] = useState<AnalysisResult | null>(null)
  const [demoRemediation, setDemoRemediation] = useState<string | null>(null)

  // Upload section state
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadAnalysis, setUploadAnalysis] = useState<AnalysisResult | null>(null)
  const [uploadRemediation, setUploadRemediation] = useState<string | null>(null)
  const [trialRemaining, setTrialRemaining] = useState(100)
  const [pasteText, setPasteText] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const runDemo = async (scenarioId: string) => {
    setActiveScenario(scenarioId)
    setDemoLoading(true)
    setDemoError(null)
    setDemoAnalysis(null)
    setDemoRemediation(null)
    try {
      const res: DemoResponse = await analyzeDemo(scenarioId)
      setDemoAnalysis(res.analysis)
      setDemoRemediation(res.remediation_command)
    } catch (e: unknown) {
      setDemoError(e instanceof Error ? e.message : 'Demo analysis failed')
    } finally {
      setDemoLoading(false)
    }
  }

  const handleFiles = async (files: File[]) => {
    if (!files.length) return
    if (trialRemaining <= 0) return
    setUploadLoading(true)
    setUploadError(null)
    setUploadAnalysis(null)
    setUploadRemediation(null)
    try {
      const res: UploadResponse = await analyzeUpload(files)
      setUploadAnalysis(res.analysis)
      setUploadRemediation(res.remediation_command)
      setTrialRemaining(res.trial_remaining ?? Math.max(0, trialRemaining - 1))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      if (msg.includes('trial limit')) setTrialRemaining(0)
      setUploadError(msg)
    } finally {
      setUploadLoading(false)
    }
  }

  const handlePaste = async () => {
    if (!pasteText.trim()) return
    if (trialRemaining <= 0) return
    setUploadLoading(true)
    setUploadError(null)
    setUploadAnalysis(null)
    setUploadRemediation(null)
    try {
      const res: UploadResponse = await analyzePaste(pasteText)
      setUploadAnalysis(res.analysis)
      setUploadRemediation(res.remediation_command)
      setTrialRemaining(res.trial_remaining ?? Math.max(0, trialRemaining - 1))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Analysis failed'
      if (msg.includes('trial limit')) setTrialRemaining(0)
      setUploadError(msg)
    } finally {
      setUploadLoading(false)
    }
  }

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const onDragLeave = useCallback(() => setIsDragging(false), [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    handleFiles(files)
  }, [trialRemaining]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen" style={{ background: '#0a0a0a', color: '#ededed' }}>
      {/* ── Navbar ── */}
      <nav className="sticky top-0 z-50 border-b border-gray-800 bg-black/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="text-white font-bold text-xl tracking-tight">
            <span className="text-green-400">⚡</span> Clarity
          </span>
          <div className="hidden md:flex items-center gap-6 text-sm text-gray-400">
            <a href="#demo" className="hover:text-white transition-colors">Demo</a>
            <a href="#upload" className="hover:text-white transition-colors">Try It</a>
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#install" className="hover:text-white transition-colors">Install</a>
          </div>
          <a
            href="#demo"
            className="px-4 py-2 rounded-lg bg-green-500 hover:bg-green-400 text-black text-sm font-semibold transition-colors"
          >
            Get Started
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden pt-24 pb-20 px-6">
        <div className="absolute inset-0 bg-gradient-to-b from-green-500/5 to-transparent pointer-events-none" />
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-green-500/30 bg-green-500/10 text-green-400 text-sm mb-6">
            🚀 Now in Public Beta
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-white leading-tight mb-6">
            Cut Incident Resolution<br />
            <span className="text-green-400">Time by 95%</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            AI-powered root cause analysis in 5 seconds instead of 4 hours.
            Upload your logs, get instant answers.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <a
              href="#demo"
              className="px-8 py-3 rounded-lg bg-green-500 hover:bg-green-400 text-black font-semibold transition-colors text-lg"
            >
              Try Live Demo →
            </a>
            <a
              href="#install"
              className="px-8 py-3 rounded-lg border-2 border-green-500 hover:bg-green-500 hover:text-black text-green-500 font-semibold transition-colors text-lg"
            >
              Install CLI
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { icon: '⚡', value: '5 seconds', label: 'to root cause' },
              { icon: '🎯', value: '95%', label: 'MTTR reduction' },
              { icon: '🔒', value: 'PII redacted', label: 'automatically' },
              { icon: '✅', value: '210 tests', label: 'passing' },
            ].map((s) => (
              <div key={s.value} className="rounded-xl border border-gray-800 bg-gray-900 p-4">
                <div className="text-2xl mb-1">{s.icon}</div>
                <div className="text-white font-bold text-lg">{s.value}</div>
                <div className="text-gray-500 text-xs">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Demo Section ── */}
      <section id="demo" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">See Clarity In Action</h2>
            <p className="text-gray-400 text-lg max-w-xl mx-auto">
              No signup required. Click a scenario to watch AI analyze a real incident.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {SCENARIOS.map((s) => (
              <div
                key={s.id}
                className={`rounded-xl border p-6 cursor-pointer transition-all duration-200 ${
                  activeScenario === s.id
                    ? 'border-green-500 bg-green-500/5 shadow-lg shadow-green-500/10'
                    : 'border-gray-800 bg-gray-900 hover:border-gray-600'
                }`}
                onClick={() => runDemo(s.id)}
              >
                <div className="flex items-start justify-between mb-4">
                  <span className="text-3xl">{s.icon}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[s.severity]}`}>
                    {s.severity}
                  </span>
                </div>
                <h3 className="text-white font-semibold text-lg mb-2">{s.title}</h3>
                <p className="text-gray-400 text-sm mb-4 leading-relaxed">{s.description}</p>
                <div className="space-y-2 mb-5">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span>📊</span>
                    <span>{s.events} log events</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {s.services.map((svc) => (
                      <span key={svc} className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">
                        {svc}
                      </span>
                    ))}
                  </div>
                </div>
                <button
                  className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
                    activeScenario === s.id && demoLoading
                      ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                      : 'bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/30'
                  }`}
                  disabled={activeScenario === s.id && demoLoading}
                >
                  {activeScenario === s.id && demoLoading ? 'Analyzing... (may take 30s if server is waking up)' : 'Run Analysis →'}
                </button>
              </div>
            ))}
          </div>

          <AnalysisResults
            analysis={demoAnalysis}
            remediationCommand={demoRemediation}
            loading={demoLoading}
            error={demoError}
          />
        </div>
      </section>

      {/* ── Upload Section ── */}
      <section id="upload" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Try With Your Own Logs</h2>
            <p className="text-gray-400 text-lg">Upload any log file and get AI-powered root cause analysis instantly.</p>
          </div>

          {/* Security badges */}
          <div className="flex flex-wrap justify-center gap-3 mb-8">
            {[
              '🔒 PII auto-redacted',
              '🗑️ Deleted after analysis',
              '🔐 TLS encrypted',
              '🚫 Not used for training',
            ].map((b) => (
              <span key={b} className="text-xs px-3 py-1.5 rounded-full border border-gray-700 bg-gray-900 text-gray-400">
                {b}
              </span>
            ))}
          </div>

          {/* Trial counter */}
          <div className="flex items-center justify-center gap-2 mb-6">
            <span className="text-sm text-gray-400">
              {trialRemaining > 0
                ? `${trialRemaining} of 100 free analyses remaining`
                : '100 free analyses used. Install CLI for unlimited local usage.'}
            </span>
          </div>

          {trialRemaining <= 0 ? (
            <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-8 text-center">
              <h3 className="text-white font-semibold text-xl mb-2">100 Free Analyses Used</h3>
              <p className="text-gray-400 text-sm mb-6">Want unlimited analysis? Install the CLI:</p>
              <div className="bg-gray-800 p-4 rounded font-mono text-sm mb-6 max-w-md mx-auto text-left">
                <div className="text-green-400">pip install clarity-ai</div>
                <div className="text-green-400">clarity analyze logs/*.log</div>
              </div>
              <a
                href="https://github.com/kp183/clarity-agent"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block px-6 py-3 rounded-lg bg-green-500 hover:bg-green-400 text-black font-semibold transition-colors"
              >
                View on GitHub →
              </a>
            </div>
          ) : (
            <>
              {/* Drop zone */}
              <div
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
                  isDragging
                    ? 'border-green-400 bg-green-500/10'
                    : 'border-gray-700 hover:border-gray-500 bg-gray-900'
                }`}
              >
                <div className="text-4xl mb-3">📁</div>
                <p className="text-white font-medium mb-1">Drop log files here or click to browse</p>
                <p className="text-gray-500 text-sm">.log .json .jsonl .csv .txt .syslog — multiple files supported</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".log,.json,.jsonl,.csv,.txt,.syslog"
                  className="hidden"
                  onChange={(e) => handleFiles(Array.from(e.target.files || []))}
                />
              </div>

              {/* OR divider */}
              <div className="flex items-center gap-4 my-6">
                <div className="flex-1 h-px bg-gray-800" />
                <span className="text-gray-600 text-sm">OR</span>
                <div className="flex-1 h-px bg-gray-800" />
              </div>

              {/* Paste area */}
              <div className="space-y-3">
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder="Paste your logs here..."
                  rows={6}
                  className="w-full rounded-lg border border-gray-700 bg-gray-900 text-gray-300 text-sm font-mono p-4 resize-none focus:outline-none focus:border-green-500/50 placeholder-gray-600"
                />
                <button
                  onClick={handlePaste}
                  disabled={!pasteText.trim() || uploadLoading}
                  className="w-full py-3 rounded-lg bg-green-500 hover:bg-green-400 disabled:bg-gray-700 disabled:text-gray-500 text-black font-semibold transition-colors"
                >
                  {uploadLoading ? 'Analyzing... (may take 30s if server is waking up)' : 'Analyze Pasted Logs'}
                </button>
              </div>
            </>
          )}

          <AnalysisResults
            analysis={uploadAnalysis}
            remediationCommand={uploadRemediation}
            loading={uploadLoading}
            error={uploadError}
          />
        </div>
      </section>

      {/* ── Features Section ── */}
      <section id="features" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">How Clarity Works</h2>
            <p className="text-gray-400 text-lg">From raw logs to actionable remediation in seconds.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              {
                icon: '🧠',
                title: 'AI Root Cause Analysis',
                desc: 'AWS Bedrock-powered analysis identifies the exact root cause from thousands of log lines in under 5 seconds.',
              },
              {
                icon: '📋',
                title: 'Multi-Format Parsing',
                desc: 'Ingests structured JSON, plaintext, CSV, syslog, and mixed-format logs from any service or platform.',
              },
              {
                icon: '👁️',
                title: 'Proactive Monitoring',
                desc: 'Sentinel agent continuously watches your logs and alerts before incidents escalate to outages.',
              },
              {
                icon: '💬',
                title: 'Interactive Investigation',
                desc: 'Ask follow-up questions in natural language. The Co-Pilot remembers full incident context.',
              },
            ].map((f) => (
              <div key={f.title} className="rounded-xl border border-gray-800 bg-gray-900 p-6">
                <div className="text-3xl mb-4">{f.icon}</div>
                <h3 className="text-white font-semibold mb-2">{f.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Install Options Section ── */}
      <section id="install" className="py-20 px-6 border-t border-gray-800">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-4 text-white">Ready to Cut Your MTTR by 95%?</h2>
          <p className="text-gray-400 text-center mb-16 text-lg">Free and open source. Start analyzing incidents in seconds.</p>
          <div className="grid md:grid-cols-3 gap-8">
            {/* CLI Install - Recommended */}
            <div className="bg-gray-900 border-2 border-green-500 rounded-xl p-8 relative">
              <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                <span className="bg-green-500 text-black px-4 py-1 rounded-full text-sm font-bold">RECOMMENDED</span>
              </div>
              <div className="text-4xl mb-4 text-center">🖥️</div>
              <h3 className="text-2xl font-bold mb-4 text-center text-white">Install CLI</h3>
              <div className="space-y-4 mb-6">
                <div className="bg-gray-800 p-4 rounded font-mono text-sm">
                  <div className="text-gray-400 mb-2"># Install</div>
                  <div className="text-green-400">pip install clarity-ai</div>
                </div>
                <div className="bg-gray-800 p-4 rounded font-mono text-sm">
                  <div className="text-gray-400 mb-2"># Analyze logs</div>
                  <div className="text-green-400">clarity analyze logs/*.log</div>
                </div>
              </div>
              <ul className="space-y-3 mb-8 text-sm text-gray-400">
                {['Unlimited local analysis', 'Works offline', 'No data sent to cloud', 'Open source'].map((f) => (
                  <li key={f} className="flex items-start gap-2"><span className="text-green-500">✓</span>{f}</li>
                ))}
              </ul>
              <a
                href="https://github.com/kp183/clarity-agent"
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full bg-green-500 hover:bg-green-600 text-black font-bold py-3 px-6 rounded text-center transition-colors"
              >
                View on GitHub →
              </a>
            </div>

            {/* Web App */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
              <div className="text-4xl mb-4 text-center">☁️</div>
              <h3 className="text-2xl font-bold mb-4 text-center text-white">Use Web App</h3>
              <p className="text-gray-400 mb-6 text-center">Upload logs directly in your browser</p>
              <ul className="space-y-3 mb-8 text-sm text-gray-400">
                {['100 free analyses', 'No installation needed', 'Works on any device', 'PII auto-redacted'].map((f) => (
                  <li key={f} className="flex items-start gap-2"><span className="text-green-500">✓</span>{f}</li>
                ))}
              </ul>
              <a
                href="#upload"
                className="block w-full bg-gray-800 hover:bg-gray-700 text-white font-bold py-3 px-6 rounded text-center transition-colors"
              >
                Try Web App →
              </a>
            </div>

            {/* Enterprise */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
              <div className="text-4xl mb-4 text-center">🏢</div>
              <h3 className="text-2xl font-bold mb-4 text-center text-white">Enterprise</h3>
              <p className="text-gray-400 mb-6 text-center">Custom deployment and integrations</p>
              <ul className="space-y-3 mb-8 text-sm text-gray-400">
                {['On-premise deployment', 'SSO / SAML', 'Custom integrations', 'SLA + dedicated support'].map((f) => (
                  <li key={f} className="flex items-start gap-2"><span className="text-green-500">✓</span>{f}</li>
                ))}
              </ul>
              <a
                href="mailto:team@clarity.ai"
                className="block w-full bg-gray-800 hover:bg-gray-700 text-white font-bold py-3 px-6 rounded text-center transition-colors"
              >
                Contact Sales →
              </a>
            </div>
          </div>
          <p className="text-center text-gray-500 mt-12">🌟 Free and open source. No credit card required.</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-white font-bold">
            <span className="text-green-400">⚡</span> Clarity
          </span>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href="#demo" className="hover:text-gray-300 transition-colors">Demo</a>
            <a href="#install" className="hover:text-gray-300 transition-colors">Install</a>
            <a href="https://github.com/kp183/clarity-agent" target="_blank" rel="noopener noreferrer" className="hover:text-gray-300 transition-colors">GitHub</a>
            <a href="mailto:team@clarity.ai" className="hover:text-gray-300 transition-colors">Contact</a>
          </div>
          <p className="text-gray-600 text-sm">© 2025 Clarity. Free and open source.</p>
        </div>
      </footer>
    </div>
  )
}
