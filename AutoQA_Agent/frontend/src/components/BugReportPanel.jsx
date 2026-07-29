import { useState } from 'react'
import { CheckCircle2 } from 'lucide-react'

export default function BugReportPanel({ codeInsights }) {
  const [filterSeverity, setFilterSeverity] = useState('ALL')

  const issues  = codeInsights?.issues || []
  const summary = codeInsights?.issues_summary || {}

  const highCount   = summary.high   ?? issues.filter(i => i.severity === 'high').length
  const mediumCount = summary.medium ?? issues.filter(i => i.severity === 'medium').length
  const lowCount    = summary.low    ?? issues.filter(i => i.severity === 'low').length

  const filteredIssues = issues.filter(issue =>
    filterSeverity === 'ALL' || issue.severity?.toLowerCase() === filterSeverity.toLowerCase()
  )

  /* ── Severity chip helper ── */
  function SeverityChip({ id, label, count, color, dimBg, activeBg, activeBorder }) {
    const isActive = filterSeverity === id
    return (
      <button
        onClick={() => setFilterSeverity(id)}
        style={{
          display: 'flex', alignItems: 'center', gap: 7,
          padding: '5px 13px', borderRadius: 8,
          background: isActive ? activeBg : dimBg,
          border: `1px solid ${isActive ? activeBorder : 'transparent'}`,
          color,
          fontSize: 12, fontWeight: 700,
          cursor: 'pointer', transition: 'all 0.15s',
          letterSpacing: '-0.01em',
        }}
        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = activeBg }}
        onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = dimBg }}
      >
        {count} {label}
      </button>
    )
  }

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.45s ease both',
    }}>
      {/* ── Filter chip bar ── */}
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      }}>
        <SeverityChip
          id="high"   label="High"   count={highCount}
          color="#ef4444"
          dimBg="rgba(239,68,68,0.1)"
          activeBg="rgba(239,68,68,0.2)"
          activeBorder="rgba(239,68,68,0.5)"
        />
        <SeverityChip
          id="medium" label="Medium" count={mediumCount}
          color="#f59e0b"
          dimBg="rgba(245,158,11,0.1)"
          activeBg="rgba(245,158,11,0.2)"
          activeBorder="rgba(245,158,11,0.5)"
        />
        <SeverityChip
          id="low"    label="Low"    count={lowCount}
          color="#10b981"
          dimBg="rgba(16,185,129,0.1)"
          activeBg="rgba(16,185,129,0.2)"
          activeBorder="rgba(16,185,129,0.5)"
        />

        {filterSeverity !== 'ALL' && (
          <button
            onClick={() => setFilterSeverity('ALL')}
            style={{
              marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)',
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px 8px',
              borderRadius: 6, transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
          >
            Clear filter
          </button>
        )}
      </div>

      {/* ── Issues table ── */}
      {filteredIssues.length === 0 ? (
        <div style={{ padding: '56px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <CheckCircle2 size={32} color="#10B981" style={{ margin: '0 auto 12px' }} />
          <p style={{ fontSize: 14, fontWeight: 600, color: '#34D399' }}>No issues detected</p>
          <p style={{ fontSize: 12, marginTop: 6 }}>
            {filterSeverity === 'ALL'
              ? 'Static analysis found 0 smells or linter errors'
              : `No ${filterSeverity} severity issues`}
          </p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'rgba(0,0,0,0.25)' }}>
                {['SEVERITY', 'FILE', 'ISSUE', 'SUGGESTION'].map(h => (
                  <th key={h} style={{
                    padding: '11px 20px', textAlign: 'left',
                    fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                    letterSpacing: '0.1em',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredIssues.map((issue, idx) => {
                const isHigh = issue.severity === 'high'
                const isMed  = issue.severity === 'medium'
                const [badgeBg, badgeColor, badgeBorder] = isHigh
                  ? ['rgba(239,68,68,0.15)',   '#ef4444', 'rgba(239,68,68,0.3)']
                  : isMed
                    ? ['rgba(245,158,11,0.15)', '#f59e0b', 'rgba(245,158,11,0.3)']
                    : ['rgba(16,185,129,0.12)', '#10b981', 'rgba(16,185,129,0.3)']

                return (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--border-soft)',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {/* Severity badge */}
                    <td style={{ padding: '12px 20px', whiteSpace: 'nowrap' }}>
                      <span style={{
                        fontSize: 10, fontWeight: 800, padding: '3px 9px', borderRadius: 6,
                        background: badgeBg, color: badgeColor, border: `1px solid ${badgeBorder}`,
                        letterSpacing: '0.05em', textTransform: 'uppercase',
                      }}>
                        {isHigh ? 'High' : isMed ? 'Medium' : 'Low'}
                      </span>
                    </td>

                    {/* File path */}
                    <td style={{ padding: '12px 20px', whiteSpace: 'nowrap' }}>
                      <span className="mono-code" style={{ fontSize: 11 }}>
                        {issue.file}{issue.line ? `:${issue.line}` : ''}
                      </span>
                    </td>

                    {/* Issue description */}
                    <td style={{ padding: '12px 20px', color: 'var(--text-primary)', fontWeight: 500, minWidth: 220 }}>
                      <div style={{ lineHeight: 1.5 }}>{issue.message}</div>
                      {issue.rule && (
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                          Rule: <span className="mono-code" style={{ fontSize: 10 }}>{issue.rule}</span>
                        </div>
                      )}
                    </td>

                    {/* Suggestion */}
                    <td style={{ padding: '12px 20px', color: 'var(--text-secondary)', fontSize: 12, minWidth: 240, lineHeight: 1.55 }}>
                      {issue.suggestion || '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
