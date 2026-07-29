import { useState, useEffect } from 'react'
import { getChangeImpact } from '../api/client'
import { AlertTriangle, ArrowRight, ShieldAlert, FileText, Globe, Layers, Database } from 'lucide-react'

export default function ImpactAnalysisTab({ analysisId, fileList = [] }) {
  const [selectedFile, setSelectedFile] = useState(fileList[0] || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (fileList.length > 0 && !selectedFile) {
      setSelectedFile(fileList[0])
    }
  }, [fileList])

  useEffect(() => {
    if (!analysisId || !selectedFile) return
    fetchImpact(selectedFile)
  }, [analysisId, selectedFile])

  async function fetchImpact(file) {
    setLoading(true)
    setError('')
    try {
      const data = await getChangeImpact(analysisId, file)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const riskColors = {
    CRITICAL: { bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.4)', text: '#f87171' },
    HIGH:     { bg: 'rgba(249,115,22,0.12)', border: 'rgba(249,115,22,0.4)', text: '#fb923c' },
    MEDIUM:   { bg: 'rgba(234,179,8,0.12)', border: 'rgba(234,179,8,0.4)', text: '#facc15' },
    LOW:      { bg: 'rgba(20,210,160,0.12)', border: 'rgba(20,210,160,0.3)', text: 'var(--accent-teal)' },
  }

  const currentRisk = result ? (riskColors[result.risk_level] || riskColors.LOW) : riskColors.LOW

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto', animation: 'fadeIn 0.3s ease both' }}>
      
      {/* File selector header */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '20px 24px',
        marginBottom: 24,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 20,
      }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
            Change Impact Analyzer
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
            Select any file to simulate modifications and predict downstream component impact.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>Target File:</label>
          <select
            value={selectedFile}
            onChange={e => setSelectedFile(e.target.value)}
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '8px 14px',
              color: 'var(--text-primary)',
              fontSize: 13,
              fontFamily: "'Fira Code', monospace",
              outline: 'none',
              cursor: 'pointer',
              maxWidth: 360,
            }}
          >
            {fileList.map(f => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)', fontSize: 13 }}>
          Analyzing change propagation paths…
        </div>
      )}

      {error && (
        <div style={{ padding: 16, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, color: '#f87171' }}>
          ⚠️ {error}
        </div>
      )}

      {!loading && result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Risk Overview Banner */}
          <div style={{
            background: currentRisk.bg,
            border: `1px solid ${currentRisk.border}`,
            borderRadius: 12,
            padding: '20px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <ShieldAlert size={32} style={{ color: currentRisk.text }} />
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: currentRisk.text, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  CHANGE RISK LEVEL: {result.risk_level}
                </div>
                <div style={{ fontSize: 14, color: 'var(--text-primary)', fontWeight: 600, marginTop: 2 }}>
                  {result.explanation}
                </div>
              </div>
            </div>

            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 28, fontWeight: 900, color: currentRisk.text, fontFamily: "'Fira Code', monospace" }}>
                {result.impact_score}<span style={{ fontSize: 14 }}>/100</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.06em' }}>
                IMPACT SCORE
              </div>
            </div>
          </div>

          {/* Grid of Affected Components */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            
            {/* Impacted Routes */}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Globe size={16} style={{ color: 'var(--accent-teal)' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Affected API Routes</span>
                <span style={{ fontSize: 11, background: 'rgba(20,210,160,0.15)', color: 'var(--accent-teal)', padding: '1px 6px', borderRadius: 99, marginLeft: 'auto', fontWeight: 700 }}>
                  {result.impacted_routes.length}
                </span>
              </div>
              {result.impacted_routes.length === 0 ? (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No API routes directly impacted.</span>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {result.impacted_routes.map(r => (
                    <div key={r} style={{ fontSize: 12, fontFamily: "'Fira Code', monospace", color: 'var(--text-secondary)', background: 'var(--bg-elevated)', padding: '6px 10px', borderRadius: 6 }}>
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Impacted Services */}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Layers size={16} style={{ color: '#a5b4fc' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Affected Services</span>
                <span style={{ fontSize: 11, background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', padding: '1px 6px', borderRadius: 99, marginLeft: 'auto', fontWeight: 700 }}>
                  {result.impacted_services.length}
                </span>
              </div>
              {result.impacted_services.length === 0 ? (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No service modules affected.</span>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {result.impacted_services.map(s => (
                    <div key={s} style={{ fontSize: 12, fontFamily: "'Fira Code', monospace", color: '#a5b4fc', background: 'var(--bg-elevated)', padding: '6px 10px', borderRadius: 6 }}>
                      {s}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Impacted Modules */}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Database size={16} style={{ color: '#facc15' }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Affected Modules</span>
                <span style={{ fontSize: 11, background: 'rgba(234,179,8,0.15)', color: '#facc15', padding: '1px 6px', borderRadius: 99, marginLeft: 'auto', fontWeight: 700 }}>
                  {result.impacted_modules.length}
                </span>
              </div>
              {result.impacted_modules.length === 0 ? (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No modules affected.</span>
              ) : (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {result.impacted_modules.map(m => (
                    <span key={m} style={{ fontSize: 11, fontWeight: 600, color: '#facc15', background: 'rgba(234,179,8,0.1)', padding: '4px 8px', borderRadius: 6 }}>
                      {m}
                    </span>
                  ))}
                </div>
              )}
            </div>

          </div>

          {/* Impacted Files Propagation Table */}
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 20 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 14px' }}>
              Downstream Dependent Files ({result.impacted_files.length})
            </h4>

            {result.impacted_files.length === 0 ? (
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>This file is leaf node — no downstream files depend on it.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {result.impacted_files.map(item => (
                  <div key={item.file_path} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', background: 'var(--bg-elevated)', borderRadius: 8,
                    border: '1px solid var(--border)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <FileText size={14} style={{ color: 'var(--text-muted)' }} />
                      <span style={{ fontSize: 13, fontFamily: "'Fira Code', monospace", color: 'var(--text-primary)' }}>
                        {item.file_path}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>
                        {item.distance}-hop ({item.impact_type})
                      </span>
                      <span style={{
                        fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
                        background: item.risk_score >= 0.7 ? 'rgba(239,68,68,0.15)' : 'rgba(20,210,160,0.15)',
                        color: item.risk_score >= 0.7 ? '#f87171' : 'var(--accent-teal)'
                      }}>
                        Risk: {Math.round(item.risk_score * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}

    </div>
  )
}
