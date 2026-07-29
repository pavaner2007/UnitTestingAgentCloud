import { useState, useEffect } from 'react'
import { getArchitectureDrift } from '../api/client'
import { ShieldAlert, AlertTriangle, Lightbulb, CheckCircle2, ChevronRight } from 'lucide-react'

export default function ArchitectureDriftTab({ analysisId, reportData }) {
  const [drift, setDrift] = useState(reportData?.architecture_drift || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!drift && analysisId) {
      setLoading(true)
      getArchitectureDrift(analysisId)
        .then(data => setDrift(data))
        .catch(err => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [analysisId, drift])

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Auditing architecture rules…</div>
  }

  if (error) {
    return <div style={{ padding: 24, color: '#f87171' }}>⚠️ {error}</div>
  }

  if (!drift) return null

  const violations = drift.violations || []
  const criticals = violations.filter(v => v.severity === 'CRITICAL')
  const warnings = violations.filter(v => v.severity === 'WARNING')
  const suggestions = violations.filter(v => v.severity === 'SUGGESTION')

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto', animation: 'fadeIn 0.3s ease both' }}>
      
      {/* Overview Card */}
      <div style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '24px',
        marginBottom: 24,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
            Architecture Drift & Violation Audit
          </h3>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '6px 0 0' }}>
            {drift.summary}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ padding: '8px 16px', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#f87171', fontFamily: "'Fira Code', monospace" }}>{drift.critical_count}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#f87171' }}>CRITICAL</div>
          </div>
          <div style={{ padding: '8px 16px', background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)', borderRadius: 8, textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#fb923c', fontFamily: "'Fira Code', monospace" }}>{drift.warning_count}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#fb923c' }}>WARNING</div>
          </div>
          <div style={{ padding: '8px 16px', background: 'rgba(234,179,8,0.12)', border: '1px solid rgba(234,179,8,0.3)', borderRadius: 8, textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#facc15', fontFamily: "'Fira Code', monospace" }}>{drift.suggestion_count}</div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#facc15' }}>SUGGESTION</div>
          </div>
        </div>
      </div>

      {violations.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, color: 'var(--accent-teal)' }}>
          <CheckCircle2 size={40} style={{ marginBottom: 12 }} />
          <h4 style={{ fontSize: 16, margin: 0, fontWeight: 700 }}>Architecture Compliance Verified</h4>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>No design rule violations or boundary drift detected.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {/* Critical Section */}
          {criticals.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <ShieldAlert size={18} style={{ color: '#f87171' }} />
                <h4 style={{ fontSize: 15, fontWeight: 800, color: '#f87171', margin: 0 }}>Critical Architecture Violations</h4>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {criticals.map((v, i) => <ViolationCard key={i} item={v} accent="#f87171" bg="rgba(239,68,68,0.06)" border="rgba(239,68,68,0.25)" />)}
              </div>
            </div>
          )}

          {/* Warning Section */}
          {warnings.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <AlertTriangle size={18} style={{ color: '#fb923c' }} />
                <h4 style={{ fontSize: 15, fontWeight: 800, color: '#fb923c', margin: 0 }}>Architectural Warnings</h4>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {warnings.map((v, i) => <ViolationCard key={i} item={v} accent="#fb923c" bg="rgba(249,115,22,0.06)" border="rgba(249,115,22,0.25)" />)}
              </div>
            </div>
          )}

          {/* Suggestion Section */}
          {suggestions.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Lightbulb size={18} style={{ color: '#facc15' }} />
                <h4 style={{ fontSize: 15, fontWeight: 800, color: '#facc15', margin: 0 }}>Design & Decoupling Suggestions</h4>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {suggestions.map((v, i) => <ViolationCard key={i} item={v} accent="#facc15" bg="rgba(234,179,8,0.06)" border="rgba(234,179,8,0.25)" />)}
              </div>
            </div>
          )}

        </div>
      )}

    </div>
  )
}

function ViolationCard({ item, accent, bg, border }) {
  return (
    <div style={{
      background: bg,
      border: `1px solid ${border}`,
      borderRadius: 10,
      padding: '18px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>{item.title}</span>
        <span style={{ fontSize: 10, fontWeight: 800, color: accent, background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: 4, fontFamily: "'Fira Code', monospace" }}>
          {item.rule_id}
        </span>
      </div>

      <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        <strong>Reason:</strong> {item.reason}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 4 }}>
        <div style={{ background: 'var(--bg-elevated)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>EXPECTED ARCHITECTURE</div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{item.expected_architecture}</div>
        </div>

        <div style={{ background: 'var(--bg-elevated)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: accent, marginBottom: 2 }}>SUGGESTED REMEDIATION</div>
          <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{item.suggested_fix}</div>
        </div>
      </div>

      {item.violating_files && item.violating_files.length > 0 && (
        <div style={{ marginTop: 4 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>VIOLATING FILES</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {item.violating_files.map(f => (
              <span key={f} style={{ fontSize: 11, fontFamily: "'Fira Code', monospace", color: accent, background: 'var(--bg-elevated)', padding: '3px 8px', borderRadius: 4, border: '1px solid var(--border)' }}>
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
