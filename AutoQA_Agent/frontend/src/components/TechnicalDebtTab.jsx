import { useState, useEffect } from 'react'
import { getTechnicalDebt } from '../api/client'
import { Wrench, AlertTriangle, ShieldAlert, Clock, ArrowUpRight, CheckCircle2 } from 'lucide-react'

export default function TechnicalDebtTab({ analysisId, reportData }) {
  const [debt, setDebt] = useState(reportData?.technical_debt || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('ALL')

  useEffect(() => {
    if (!debt && analysisId) {
      setLoading(true)
      getTechnicalDebt(analysisId)
        .then(data => setDebt(data))
        .catch(err => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [analysisId, debt])

  if (loading) return <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Prioritizing technical debt items by risk & effort…</div>
  if (error) return <div style={{ padding: 24, color: '#f87171' }}>⚠️ {error}</div>
  if (!debt) return null

  const items = debt.items || []
  const filtered = categoryFilter === 'ALL' ? items : items.filter(i => i.category === categoryFilter)

  const sevColors = {
    CRITICAL: { bg: 'rgba(239,68,68,0.15)', text: '#f87171', border: 'rgba(239,68,68,0.3)' },
    HIGH:     { bg: 'rgba(249,115,22,0.15)', text: '#fb923c', border: 'rgba(249,115,22,0.3)' },
    MEDIUM:   { bg: 'rgba(234,179,8,0.15)', text: '#facc15', border: 'rgba(234,179,8,0.3)' },
    LOW:      { bg: 'rgba(20,210,160,0.15)', text: 'var(--accent-teal)', border: 'rgba(20,210,160,0.3)' },
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto', animation: 'fadeIn 0.3s ease both' }}>
      
      {/* Header Banner */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ padding: 12, borderRadius: 10, background: 'rgba(249,115,22,0.15)', color: '#fb923c' }}>
            <Wrench size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Prioritized Technical Debt Backlog
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
              Ranked automatically using Priority Matrix: (Severity Weight × Business Risk) / Fix Effort.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 22, fontWeight: 900, color: '#fb923c', fontFamily: "'Fira Code', monospace" }}>
              ~{debt.estimated_total_fix_hours} hrs
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700 }}>ESTIMATED FIX EFFORT</div>
          </div>
        </div>
      </div>

      {/* Filter Category Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)' }}>Category Filter:</span>
        {['ALL', 'Security', 'Bug', 'Architecture Drift', 'Tech Debt'].map(cat => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: categoryFilter === cat ? 'var(--accent-teal)' : 'var(--bg-surface)',
              color: categoryFilter === cat ? '#0a1628' : 'var(--text-primary)',
              border: categoryFilter === cat ? 'none' : '1px solid var(--border)',
              cursor: 'pointer', transition: 'all 0.15s'
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Debt Backlog List */}
      {filtered.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, color: 'var(--accent-teal)' }}>
          <CheckCircle2 size={40} style={{ marginBottom: 12 }} />
          <h4 style={{ fontSize: 16, margin: 0, fontWeight: 700 }}>No Technical Debt Items Found</h4>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>All issues resolved for this filter category.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {filtered.map(item => {
            const sev = sevColors[item.severity] || sevColors.MEDIUM

            return (
              <div key={item.rank} style={{
                background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 20,
                display: 'flex', flexDirection: 'column', gap: 12
              }}>
                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      width: 28, height: 28, borderRadius: '50%', background: 'rgba(255,255,255,0.06)',
                      color: 'var(--text-primary)', fontWeight: 900, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      #{item.rank}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>{item.title}</span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: sev.bg, color: sev.text, border: `1px solid ${sev.border}` }}>
                      {item.severity}
                    </span>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 4, background: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
                      {item.category}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--accent-teal)', fontFamily: "'Fira Code', monospace", fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={12} /> {item.estimated_fix_time}
                    </span>
                  </div>
                </div>

                {/* Reason & Location */}
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <strong style={{ color: 'var(--text-primary)' }}>Why fix first:</strong> {item.why_fix_first}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-elevated)', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>
                    <strong>Remediation:</strong> {item.suggested_fix}
                  </div>
                  <div style={{ fontSize: 11, fontFamily: "'Fira Code', monospace", color: 'var(--text-muted)', flexShrink: 0, marginLeft: 16 }}>
                    {item.file_path}{item.line_number ? `:${item.line_number}` : ''}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

    </div>
  )
}
