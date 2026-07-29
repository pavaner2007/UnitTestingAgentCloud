import { useState, useEffect } from 'react'
import { getRepositoryHealth } from '../api/client'
import { Activity, ShieldCheck, CheckCircle2, AlertTriangle, Lightbulb, BarChart2 } from 'lucide-react'

export default function RepositoryHealthTab({ analysisId, reportData }) {
  const [health, setHealth] = useState(reportData?.repository_health || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!health && analysisId) {
      setLoading(true)
      getRepositoryHealth(analysisId)
        .then(data => setHealth(data))
        .catch(err => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [analysisId, health])

  if (loading) return <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Calculating 8-category repository health score…</div>
  if (error) return <div style={{ padding: 24, color: '#f87171' }}>⚠️ {error}</div>
  if (!health) return null

  const categories = health.category_scores || []
  const overall = health.overall_score || 0

  const scoreColor = overall >= 85 ? 'var(--accent-teal)' : overall >= 65 ? '#facc15' : '#f87171'

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto', animation: 'fadeIn 0.3s ease both' }}>
      
      {/* Top Banner with Score Gauge */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 16, padding: 28, marginBottom: 24,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 32
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <Activity size={24} style={{ color: scoreColor }} />
            <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', margin: 0 }}>
              Repository Quality & Health Dashboard
            </h3>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            Comprehensive quality assessment evaluating architecture, security, maintainability, performance, documentation, testing, complexity, and technical debt.
          </p>
        </div>

        {/* Large Score Circle / Gauge */}
        <div style={{
          width: 110, height: 110, borderRadius: '50%',
          background: `radial-gradient(circle, var(--bg-surface) 60%, ${scoreColor}22 100%)`,
          border: `4px solid ${scoreColor}`,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, boxShadow: `0 0 20px ${scoreColor}33`
        }}>
          <div style={{ fontSize: 32, fontWeight: 900, color: scoreColor, fontFamily: "'Fira Code', monospace", lineHeight: 1 }}>
            {Math.round(overall)}
          </div>
          <div style={{ fontSize: 10, fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.08em', marginTop: 2 }}>
            HEALTH SCORE
          </div>
        </div>
      </div>

      {/* 8 Category Breakdown Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {categories.map(cat => {
          const cScore = cat.score || 0
          const color = cScore >= 85 ? 'var(--accent-teal)' : cScore >= 65 ? '#facc15' : '#f87171'

          return (
            <div key={cat.category} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{cat.category}</span>
                <span style={{ fontSize: 14, fontWeight: 800, color: color, fontFamily: "'Fira Code', monospace" }}>
                  {Math.round(cScore)}%
                </span>
              </div>

              {/* Progress bar */}
              <div style={{ height: 5, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden', marginBottom: 8 }}>
                <div style={{ height: '100%', width: `${cScore}%`, background: color, borderRadius: 4, transition: 'width 0.5s ease' }} />
              </div>

              <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.3 }}>
                {cat.details}
              </div>
            </div>
          )
        })}
      </div>

      {/* Strengths, Weaknesses & Recommendations */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        
        {/* Strengths & Weaknesses */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          
          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
            <h4 style={{ fontSize: 14, fontWeight: 800, color: 'var(--accent-teal)', margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <CheckCircle2 size={16} /> Architectural & Code Strengths
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {health.strengths.map((str, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--text-primary)', background: 'var(--bg-elevated)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
                  ✓ {str}
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
            <h4 style={{ fontSize: 14, fontWeight: 800, color: '#f87171', margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertTriangle size={16} /> Vulnerabilities & Weaknesses
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {health.weaknesses.map((wk, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--text-primary)', background: 'var(--bg-elevated)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
                  ⚠️ {wk}
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Actionable Recommendations */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
          <h4 style={{ fontSize: 14, fontWeight: 800, color: '#facc15', margin: '0 0 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Lightbulb size={16} /> Actionable Improvement Plan
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {health.actionable_recommendations.map((rec, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, padding: '10px 14px', background: 'var(--bg-elevated)', borderRadius: 8, border: '1px solid var(--border)' }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: '#facc15', background: 'rgba(234,179,8,0.15)', width: 20, height: 20, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                  {rec}
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  )
}
