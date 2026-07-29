import { useState } from 'react'
import { Code2, Zap, AlertCircle, FileCode, FolderOpen, SkipForward, ShieldAlert, CheckCircle2, Filter } from 'lucide-react'

// ── Helper components ────────────────────────────────────────────────────────

function SkipProportionBar({ analyzedCount, skippedCount, skippedBreakdown = {} }) {
  const total = analyzedCount + skippedCount
  if (total === 0) return null

  const vendorCount = skippedBreakdown.excluded_vendor || 0
  const budgetCount = skippedBreakdown.excluded_token_budget || 0
  const binaryCount = (skippedBreakdown.excluded_binary || 0) + (skippedBreakdown.excluded_lockfile || 0)
  const otherCount = Math.max(0, skippedCount - (vendorCount + budgetCount + binaryCount))

  const segments = [
    { label: 'Analyzed', count: analyzedCount, color: '#10B981' },
    { label: 'Vendor / Deps', count: vendorCount, color: '#64748B' },
    { label: 'Budget Cap', count: budgetCount, color: '#F59E0B' },
    { label: 'Binaries / Locks', count: binaryCount, color: '#3B82F6' },
    ...(otherCount > 0 ? [{ label: 'Other', count: otherCount, color: '#94A3B8' }] : []),
  ].filter(s => s.count > 0)

  return (
    <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', background: 'rgba(0,0,0,0.15)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileCode size={14} color="#10B981" />
          File Coverage Breakdown
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>
            ({analyzedCount} selected / {total} total files)
          </span>
        </div>
        <span className="mono-code" style={{ fontSize: 10 }}>
          {Math.round((analyzedCount / total) * 100)}% Coverage
        </span>
      </div>

      {/* Stacked bar */}
      <div style={{
        height: 10, borderRadius: 99, display: 'flex', overflow: 'hidden',
        background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
      }}>
        {segments.map(seg => {
          const pct = (seg.count / total) * 100
          return (
            <div
              key={seg.label}
              title={`${seg.label}: ${seg.count} files (${Math.round(pct)}%)`}
              style={{
                width: `${pct}%`,
                background: seg.color,
                transition: 'width 0.6s ease',
              }}
            />
          )
        })}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10, fontSize: 11 }}>
        {segments.map(seg => (
          <div key={seg.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: seg.color }} />
            <span style={{ color: 'var(--text-secondary)' }}>{seg.label}:</span>
            <strong style={{ color: 'var(--text-primary)' }}>{seg.count}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

function PatternBadge({ pattern }) {
  let color = '#94A3B8'
  if (/JWT auth|OAuth|login/i.test(pattern))   color = '#F59E0B'
  if (/Raw SQL/i.test(pattern))                color = '#EF4444'
  if (/External API/i.test(pattern))           color = '#06B6D4'
  if (/Env\/secrets/i.test(pattern))           color = '#10B981'
  if (/Subprocess/i.test(pattern))            color = '#EC4899'
  if (/File I\/O/i.test(pattern))              color = '#8B5CF6'
  if (/Hardcoded secret/i.test(pattern))       color = '#DC2626'
  if (/TODO|FIXME/i.test(pattern))             color = '#EAB308'

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10,
      padding: '9px 12px', borderRadius: 8,
      background: `${color}08`, border: `1px solid ${color}1a`,
    }}>
      <span style={{ color, fontFamily: 'monospace', fontSize: 11, flexShrink: 0, marginTop: 1 }}>›</span>
      <span className="mono-code" style={{ fontSize: 12, background: 'transparent', border: 'none', padding: 0 }}>
        {pattern}
      </span>
    </div>
  )
}

function ModuleRow({ name, summary }) {
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 9,
      background: 'rgba(6,182,212,0.04)',
      border: '1px solid rgba(6,182,212,0.12)',
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <span className="mono-code" style={{ color: '#67E8F9', fontWeight: 700 }}>{name}/</span>
      <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{summary}</span>
    </div>
  )
}

function IssueRow({ issue }) {
  const sevColors = {
    high: '#EF4444',
    medium: '#F59E0B',
    low: '#10B981',
  }
  const color = sevColors[issue.severity] || '#94A3B8'

  return (
    <div style={{
      padding: '10px 14px', borderRadius: 10,
      background: `${color}08`,
      border: `1px solid ${color}20`,
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
            background: `${color}20`, color, textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            {issue.severity}
          </span>
          <span className="mono-code" style={{ fontSize: 11 }}>
            [{issue.rule}]
          </span>
        </div>
        <span className="mono-code" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {issue.file}{issue.line ? `:${issue.line}` : ''}
        </span>
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
        {issue.message}
      </p>
    </div>
  )
}

// ── Main panel ───────────────────────────────────────────────────────────────

export default function CodeInsightsPanel({ codeInsights }) {
  const [tab, setTab] = useState('health')
  const [severityFilter, setSeverityFilter] = useState('all')

  if (!codeInsights) return null

  const {
    analyzed_files = [],
    skipped_files_count = 0,
    skipped_files_breakdown = {},
    file_summaries = {},
    module_summaries = {},
    notable_patterns = [],
    cache_hit_rate = 0,
    issues = [],
    issues_summary = {},
  } = codeInsights

  const cachePct = Math.round(cache_hit_rate * 100)
  const hasPatterns = notable_patterns.length > 0
  const hasModules  = Object.keys(module_summaries).length > 0
  const hasIssues   = issues.length > 0

  const tabs = [
    { id: 'health',   label: 'Code Health', count: issues.length },
    ...(hasPatterns ? [{ id: 'patterns', label: 'Patterns',    count: notable_patterns.length }] : []),
    ...(hasModules  ? [{ id: 'modules',  label: 'Modules',     count: Object.keys(module_summaries).length }] : []),
  ]
  const activeTab = tabs.some(t => t.id === tab) ? tab : 'health'

  const filteredIssues = issues.filter(i => severityFilter === 'all' || i.severity === severityFilter)

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.3s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'linear-gradient(90deg, rgba(99,102,241,0.06) 0%, transparent 60%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'rgba(99,102,241,0.12)',
            border: '1px solid rgba(99,102,241,0.22)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Code2 size={16} color="#A5B4FC" />
          </div>
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>Code Insights & Quality</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              Deterministic static smells + ruff linter + pattern analysis
            </p>
          </div>
        </div>

        {/* Cache hit rate badge */}
        {cachePct > 0 && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '3px 9px', borderRadius: 99,
            background: 'rgba(16,185,129,0.1)', color: '#6EE7B7',
            border: '1px solid rgba(16,185,129,0.2)', letterSpacing: '0.04em',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <Zap size={10} />
            {cachePct}% cached
          </span>
        )}
      </div>

      {/* Skip ratio proportion bar */}
      <SkipProportionBar
        analyzedCount={analyzed_files.length}
        skippedCount={skipped_files_count}
        skippedBreakdown={skipped_files_breakdown}
      />

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
        padding: '0 24px', overflowX: 'auto', background: 'rgba(0,0,0,0.1)',
      }}>
        {tabs.map(({ id, label, count }) => {
          const isActive = activeTab === id
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '12px 16px', background: 'transparent', border: 'none',
                borderBottom: isActive ? '2px solid #6366F1' : '2px solid transparent',
                color: isActive ? '#A5B4FC' : 'var(--text-muted)',
                fontSize: 13, fontWeight: isActive ? 700 : 500,
                cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                transition: 'all 0.15s', whiteSpace: 'nowrap', marginBottom: -1,
              }}
            >
              {label}
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 99,
                background: isActive ? 'rgba(99,102,241,0.2)' : 'rgba(148,163,184,0.1)',
                color: isActive ? '#A5B4FC' : 'var(--text-muted)',
                fontWeight: 700,
              }}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      <div style={{ padding: '20px 24px', animation: 'fadeIn 0.2s ease' }} key={activeTab}>
        {/* Code Health tab */}
        {activeTab === 'health' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Health Bar Summary */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Detected Issues:
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: 'rgba(239,68,68,0.12)', color: '#F87171', border: '1px solid rgba(239,68,68,0.2)',
                }}>
                  🔴 {issues_summary.high || 0} High
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: 'rgba(245,158,11,0.12)', color: '#FCD34D', border: '1px solid rgba(245,158,11,0.2)',
                }}>
                  🟡 {issues_summary.medium || 0} Medium
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: 'rgba(16,185,129,0.12)', color: '#6EE7B7', border: '1px solid rgba(16,185,129,0.2)',
                }}>
                  🟢 {issues_summary.low || 0} Low
                </span>
              </div>

              {/* Severity Filter buttons */}
              {hasIssues && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(0,0,0,0.3)', padding: 3, borderRadius: 8 }}>
                  {['all', 'high', 'medium', 'low'].map(sev => (
                    <button
                      key={sev}
                      onClick={() => setSeverityFilter(sev)}
                      style={{
                        padding: '3px 9px', borderRadius: 6, border: 'none',
                        background: severityFilter === sev ? 'rgba(255,255,255,0.1)' : 'transparent',
                        color: severityFilter === sev ? 'var(--text-primary)' : 'var(--text-muted)',
                        fontSize: 11, fontWeight: 600, textTransform: 'capitalize', cursor: 'pointer',
                      }}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Issue List */}
            {!hasIssues ? (
              <div style={{
                textAlign: 'center', padding: '32px 20px', borderRadius: 12,
                background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.15)',
              }}>
                <CheckCircle2 size={32} color="#10B981" style={{ margin: '0 auto 10px' }} />
                <div style={{ fontSize: 14, fontWeight: 700, color: '#34D399' }}>Clean Code Health</div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  No static smells or rinter warnings detected in analyzed files.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {filteredIssues.map((issue, idx) => (
                  <IssueRow key={idx} issue={issue} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Patterns tab */}
        {activeTab === 'patterns' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, fontStyle: 'italic' }}>
              Detected by deterministic regex scanner — not inferred by AI.
            </p>
            {notable_patterns.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
                No notable patterns detected
              </div>
            ) : (
              notable_patterns.map((p, i) => <PatternBadge key={i} pattern={p} />)
            )}
          </div>
        )}

        {/* Modules tab */}
        {activeTab === 'modules' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, fontStyle: 'italic' }}>
              Module summaries enriched by hierarchical code analysis (Ollama code model).
            </p>
            {Object.entries(module_summaries).map(([name, summary]) => (
              <ModuleRow key={name} name={name} summary={summary} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
