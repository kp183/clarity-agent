export interface AnalysisResult {
  summary: string
  root_cause_description: string
  affected_components: string[]
  confidence_score: number
}

export interface DemoResponse {
  demo: boolean
  scenario: string
  metadata: {
    name: string
    description: string
    severity: string
    events_count: number
    services: string[]
    root_cause: string
    remediation: string
  }
  analysis: AnalysisResult
  remediation_command: string | null
}

export interface UploadResponse {
  status: string
  session_id: string
  analysis: AnalysisResult
  remediation_command: string | null
  trial_remaining: number
}
