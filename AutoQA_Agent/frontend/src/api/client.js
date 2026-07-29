const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function analyzeRepository(githubUrl) {
  const response = await fetch(`${API_BASE_URL}/analyze-repository`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Repository analysis failed')
  }
  // Returns { analysis_id, status, cached, report? }
  return response.json()
}

export async function getAnalysisStatus(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/status`)
  if (!response.ok) return null
  return response.json()
}


export async function getAnalysis(id) {
  const response = await fetch(`${API_BASE_URL}/analysis/${id}`)
  if (!response.ok) throw new Error('Analysis not found')
  return response.json()
}

export async function getAnalyses() {
  try {
    const response = await fetch(`${API_BASE_URL}/analyses`)
    if (!response.ok) return []
    const data = await response.json()
    return Array.isArray(data) ? data : (data.analyses || [])
  } catch {
    return []
  }
}

export async function downloadPdf(analysisId, repoName) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/pdf`)
  if (!response.ok) throw new Error('PDF generation failed')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `autoqa-${repoName || analysisId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function askCodebaseQuestion(analysisId, question) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Q&A request failed')
  }
  return response.json()
}

export async function emailReport(analysisId, recipientEmail) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recipient_email: recipientEmail }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || 'Failed to send email report')
  }
  return data
}

export async function getChangeImpact(analysisId, file) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/impact?file=${encodeURIComponent(file)}`)
  if (!response.ok) throw new Error('Failed to fetch change impact analysis')
  return response.json()
}

export async function getArchitectureDrift(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/architecture-drift`)
  if (!response.ok) throw new Error('Failed to fetch architecture drift report')
  return response.json()
}

export async function compareRepositories(analysisIdA, analysisIdB) {
  const response = await fetch(`${API_BASE_URL}/compare-repositories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id_a: analysisIdA, analysis_id_b: analysisIdB }),
  })
  if (!response.ok) throw new Error('Cross-repository comparison failed')
  return response.json()
}

export async function getProjectOnboarding(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/onboarding`)
  if (!response.ok) throw new Error('Failed to fetch project onboarding guide')
  return response.json()
}

export async function getRepositoryHealth(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/health-score`)
  if (!response.ok) throw new Error('Failed to fetch repository health score')
  return response.json()
}

export async function getTechnicalDebt(analysisId) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}/technical-debt`)
  if (!response.ok) throw new Error('Failed to fetch technical debt backlog')
  return response.json()
}
