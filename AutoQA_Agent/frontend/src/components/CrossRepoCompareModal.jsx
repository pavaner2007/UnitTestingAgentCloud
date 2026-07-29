import { useState, useEffect } from 'react'
import { getAnalyses, compareRepositories } from '../api/client'
import { X, GitCompare, FileCode, CheckCircle, Percent } from 'lucide-react'

export default function CrossRepoCompareModal({ isOpen, onClose, currentAnalysisId }) {
  const [analyses, setAnalyses] = useState([])
  const [repoA, setRepoA] = useState(currentAnalysisId || '')
  const [repoB, setRepoB] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isOpen) {
      getAnalyses().then(list => {
        setAnalyses(list)
        if (currentAnalysisId) setRepoA(currentAnalysisId)
        if (list.length > 1) {
          const other = list.find(a => a.analysis_id !== currentAnalysisId)
          if (other) setRepoB(other.analysis_id)
        }
      })
    }
  }, [isOpen, currentAnalysisId])

  if (!isOpen) return null

  async function handleCompare(e) {
    e.preventDefault()
    if (!repoA || !repoB) {
      setError('Please select two repositories to compare.')
      return
    }
    if (repoA === repoB) {
      setError('Please select two distinct repositories.')
      return
    }

    setLoading(true)
    setError('')
    try {
      const data = await compareRepositories(repoA, repoB)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(5, 10, 20, 0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
      animation: 'fadeIn 0.2s ease both',
    }}>
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        width: '100%', maxWidth: 840,
        maxHeight: '90vh', overflowY: 'auto',
        padding: 28,
        position: 'relative',
        boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
      }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{ position: 'absolute', right: 20, top: 20, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
        >
          <X size={20} />
        </button>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <div style={{ padding: 10, borderRadius: 10, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
            <GitCompare size={22} />
          </div>
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Cross-Repository Comparison
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '2px 0 0' }}>
              Compare codebase architectures and detect duplicated files/functions across analyzed repos.
            </p>
          </div>
        </div>

        {/* Form Selector */}
        <form onSubmit={handleCompare} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 14, alignItems: 'end', marginBottom: 24 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>REPOSITORY A</label>
            <select
              value={repoA}
              onChange={e => setRepoA(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13 }}
            >
              <option value="">-- Select Repo A --</option>
              {analyses.map(a => (
                <option key={a.analysis_id} value={a.analysis_id}>
                  {a.repository_name} ({a.analysis_id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>REPOSITORY B</label>
            <select
              value={repoB}
              onChange={e => setRepoB(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13 }}
            >
              <option value="">-- Select Repo B --</option>
              {analyses.map(a => (
                <option key={a.analysis_id} value={a.analysis_id}>
                  {a.repository_name} ({a.analysis_id.slice(0, 8)})
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: 'var(--accent-teal)',
              color: '#0a1628',
              border: 'none',
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {loading ? 'Comparing…' : 'Compare Repos'}
          </button>
        </form>

        {error && (
          <div style={{ padding: 12, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#f87171', fontSize: 13, marginBottom: 20 }}>
            ⚠️ {error}
          </div>
        )}

        {/* Comparison Result Display */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Clone Detection Banner */}
            {result.clone_detected && result.clone_banner_message && (
              <div style={{
                background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.4)',
                borderRadius: 12, padding: '14px 18px',
                display: 'flex', alignItems: 'flex-start', gap: 12,
              }}>
                <span style={{ fontSize: '22px', flexShrink: 0 }}>⚠️</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#fca5a5', marginBottom: 4 }}>
                    Near-Identical Repository Detected
                  </div>
                  <div style={{ fontSize: 12, color: '#fca5a5bb', lineHeight: 1.6 }}>
                    {result.clone_banner_message}
                  </div>
                </div>
              </div>
            )}

            {/* High similarity (not clone threshold but still very similar) */}
            {!result.clone_detected && result.overall_similarity_percentage >= 75 && (
              <div style={{
                background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.35)',
                borderRadius: 12, padding: '12px 18px',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <span style={{ fontSize: '20px' }}>🔶</span>
                <div style={{ fontSize: 12, color: '#fcd34d', lineHeight: 1.5 }}>
                  High similarity detected — these repositories may share a common origin or template.
                </div>
              </div>
            )}

            {/* Score Banner */}
            <div style={{
              background: 'rgba(99,102,241,0.08)',
              border: '1px solid rgba(99,102,241,0.3)',
              borderRadius: 12, padding: 20,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#a5b4fc', letterSpacing: '0.08em' }}>CROSS-REPO OVERLAP SUMMARY</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
                    {result.comparison_summary}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
                  <div style={{ fontSize: 36, fontWeight: 900, color: '#a5b4fc', fontFamily: "'Fira Code', monospace" }}>
                    {result.overall_similarity_percentage}%
                  </div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>OVERALL SIMILARITY</div>
                </div>
              </div>

              {/* Relationship type */}
              {result.relationship_type && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Relationship:
                  </span>
                  <span style={{
                    fontSize: 12, fontWeight: 700, padding: '3px 12px', borderRadius: '20px',
                    background: result.clone_detected ? 'rgba(239,68,68,0.2)' :
                                result.relationship_type.includes('Fork') ? 'rgba(245,158,11,0.2)' :
                                result.relationship_type.includes('Shared') ? 'rgba(99,102,241,0.2)' :
                                'rgba(107,114,128,0.2)',
                    color: result.clone_detected ? '#f87171' :
                           result.relationship_type.includes('Fork') ? '#fcd34d' :
                           result.relationship_type.includes('Shared') ? '#a5b4fc' :
                           'var(--text-secondary)',
                    border: `1px solid ${result.clone_detected ? 'rgba(239,68,68,0.4)' : 'rgba(107,114,128,0.3)'}`,
                  }}>
                    {result.relationship_type}
                  </span>
                  {result.relationship_confidence > 0 && (
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      ({Math.round(result.relationship_confidence * 100)}% confidence)
                    </span>
                  )}
                </div>
              )}

              {/* Multi-dimensional similarity breakdown */}
              {[
                { label: 'API Similarity', value: result.api_similarity, color: '#3b82f6', icon: '🌐' },
                { label: 'Code Similarity', value: result.code_similarity, color: '#8b5cf6', icon: '💻' },
                { label: 'Architecture', value: result.architecture_similarity, color: '#10b981', icon: '🏛️' },
                { label: 'Module Structure', value: result.module_similarity, color: '#f59e0b', icon: '📦' },
                { label: 'Feature Overlap', value: result.feature_similarity, color: '#ef4444', icon: '🗺️' },
              ].filter(r => r.value !== undefined && r.value !== null).map(row => (
                <div key={row.label} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{row.icon} {row.label}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: row.color }}>{row.value}%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-app)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(100, row.value || 0)}%`, height: '100%',
                      background: row.color, borderRadius: '3px',
                      transition: 'width 0.6s ease',
                    }} />
                  </div>
                </div>
              ))}

              {/* Duplicate counts */}
              <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                {[
                  { label: 'Duplicate Files', value: result.duplicate_file_count ?? result.duplicated_files?.length ?? 0 },
                  { label: 'Duplicate Functions', value: result.duplicate_function_count ?? result.duplicated_functions?.length ?? 0 },
                ].map(m => (
                  <div key={m.label} style={{
                    flex: 1, background: 'var(--bg-app)', borderRadius: 8, padding: '8px 12px', textAlign: 'center',
                    border: '1px solid var(--border-subtle)',
                  }}>
                    <div style={{ fontSize: 20, fontWeight: 800, color: '#a5b4fc' }}>{m.value}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{m.label}</div>
                  </div>
                ))}
              </div>

              {/* Reasoning */}
              {result.relationship_reasoning && (
                <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  💡 {result.relationship_reasoning}
                </div>
              )}
            </div>

            {/* Duplicated Files & Functions */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              
              <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
                <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 12px' }}>
                  Matching File Structures ({result.duplicated_files.length})
                </h4>
                {result.duplicated_files.length === 0 ? (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No file overlap detected.</span>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {result.duplicated_files.map((item, idx) => (
                      <div key={idx} style={{ fontSize: 11, fontFamily: "'Fira Code', monospace", padding: '8px 10px', background: 'var(--bg-surface)', borderRadius: 6, display: 'flex', justifyContent: 'space-between' }}>
                        <span>{item.file_a} ↔ {item.file_b}</span>
                        <span style={{ color: 'var(--accent-teal)', fontWeight: 700 }}>{item.similarity_percentage}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
                <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 12px' }}>
                  Common API Handler Functions ({result.duplicated_functions.length})
                </h4>
                {result.duplicated_functions.length === 0 ? (
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No shared API handlers detected.</span>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {result.duplicated_functions.map((item, idx) => (
                      <div key={idx} style={{ fontSize: 11, fontFamily: "'Fira Code', monospace", padding: '8px 10px', background: 'var(--bg-surface)', borderRadius: 6, display: 'flex', justifyContent: 'space-between' }}>
                        <span>`{item.function_a}` ({item.file_a})</span>
                        <span style={{ color: '#a5b4fc', fontWeight: 700 }}>{item.similarity_percentage}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>

          </div>
        )}

      </div>
    </div>
  )
}
