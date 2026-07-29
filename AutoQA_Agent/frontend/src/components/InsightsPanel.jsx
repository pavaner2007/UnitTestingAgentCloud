import { useState } from 'react'
import { Bot, BookOpen, Workflow, Cpu, ShieldCheck, AlertTriangle } from 'lucide-react'

const TABS = [
  { id: 'summary', label: 'Summary', icon: BookOpen },
  { id: 'features', label: 'Features', icon: ShieldCheck },
  { id: 'workflow', label: 'Workflow', icon: Workflow },
  { id: 'architecture', label: 'Architecture', icon: Cpu },
]

function getConfidenceColor(score) {
  if (score == null) return '#64748B'
  if (score >= 80) return '#10B981'
  if (score >= 60) return '#F59E0B'
  return '#EF4444'
}

export default function InsightsPanel({ explanation, repoName, detectedFeatures = [], confidenceScore, architectureNotes }) {
  const [activeTab, setActiveTab] = useState('summary')

  if (!explanation) return null

  const {
    project_overview,
    workflow = [],
    key_technologies = {},
    api_summary,
    complexity_level,
    use_case,
  } = explanation

  const confColor = getConfidenceColor(confidenceScore)
  const isLowConf = confidenceScore != null && confidenceScore < 70
  const complexityColor = { Beginner: '#10B981', Intermediate: '#F59E0B', Advanced: '#EF4444' }[complexity_level] || '#94A3B8'

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.2s both',
      marginBottom: 20,
    }}>
      {/* Header */}
      <div style={{
        padding: '18px 24px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(90deg, rgba(59,130,246,0.05) 0%, transparent 60%)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'linear-gradient(135deg, rgba(59,130,246,0.25), rgba(139,92,246,0.25))',
            border: '1px solid rgba(59,130,246,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Bot size={16} color="#93C5FD" />
          </div>
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>AI Insights</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              Groq · llama-3.1-8b-instant · Structured facts only
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {confidenceScore != null && (
            <span style={{
              fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 99,
              background: `${confColor}18`, color: confColor, border: `1px solid ${confColor}30`,
            }}>
              {Math.round(confidenceScore)}% confidence
            </span>
          )}
          {complexity_level && (
            <span style={{
              fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 99,
              background: `${complexityColor}18`, color: complexityColor, border: `1px solid ${complexityColor}30`,
            }}>
              {complexity_level}
            </span>
          )}
        </div>
      </div>

      {/* Low confidence warning */}
      {isLowConf && (
        <div style={{
          margin: '0', padding: '10px 24px',
          background: 'rgba(245,158,11,0.06)',
          borderBottom: '1px solid rgba(245,158,11,0.2)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <AlertTriangle size={14} color="#FCD34D" />
          <span style={{ fontSize: 12, color: '#FCD34D', fontWeight: 600 }}>
            Low confidence ({Math.round(confidenceScore)}%) — Limited evidence found. Manual review recommended.
          </span>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 0,
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        overflowX: 'auto',
      }}>
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = activeTab === id
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '12px 16px',
                background: 'transparent', border: 'none',
                borderBottom: isActive ? '2px solid #3B82F6' : '2px solid transparent',
                color: isActive ? '#93C5FD' : 'var(--text-muted)',
                fontSize: 13, fontWeight: isActive ? 600 : 500,
                cursor: 'pointer', fontFamily: 'Inter, sans-serif',
                transition: 'all 0.15s', whiteSpace: 'nowrap',
                marginBottom: -1,
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)' }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-muted)' }}
            >
              <Icon size={13} />
              {label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div style={{ padding: '24px', animation: 'fadeIn 0.25s ease' }} key={activeTab}>

        {/* SUMMARY TAB */}
        {activeTab === 'summary' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {project_overview && (
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.75, maxWidth: 720 }}>
                {project_overview}
              </p>
            )}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {use_case && (
                <InfoChip label="Use Case" value={use_case} color="#6366F1" />
              )}
              {api_summary && (
                <InfoChip label="API Layer" value={api_summary} color="#06B6D4" />
              )}
            </div>
            {/* Key Technologies inline */}
            {Object.keys(key_technologies).length > 0 && (
              <div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10 }}>
                  Key Technologies Explained
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
                  {Object.entries(key_technologies).map(([tech, desc]) => (
                    <div key={tech} style={{
                      padding: '12px 14px', borderRadius: 10,
                      background: 'rgba(167,139,250,0.05)',
                      border: '1px solid rgba(167,139,250,0.12)',
                    }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#C4B5FD', marginBottom: 4 }}>{tech}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* FEATURES TAB */}
        {activeTab === 'features' && (
          <div>
            {detectedFeatures.length === 0 ? (
              <EmptyState message="No features detected" />
            ) : (
              <div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, fontStyle: 'italic' }}>
                  Detected from code evidence only — not inferred from repository name.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
                  {detectedFeatures.map(f => (
                    <div key={f.name} style={{
                      padding: '14px 16px', borderRadius: 10,
                      background: 'rgba(16,185,129,0.04)',
                      border: '1px solid rgba(16,185,129,0.14)',
                    }}>
                      <div style={{
                        fontSize: 12, fontWeight: 700, color: '#6EE7B7',
                        marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
                      }}>
                        <ShieldCheck size={12} />
                        {f.name}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {(f.evidence || []).map((ev, i) => (
                          <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                            <span style={{ color: 'rgba(16,185,129,0.5)', fontSize: 10, flexShrink: 0 }}>›</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', lineHeight: 1.5 }}>
                              {ev}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* WORKFLOW TAB */}
        {activeTab === 'workflow' && (
          <div>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 18 }}>
              Detected Workflow
            </p>
            {workflow.length === 0 ? (
              <EmptyState message="No workflow steps detected" />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {workflow.map((step, i) => (
                  <div key={i} style={{ display: 'flex', gap: 0, alignItems: 'stretch' }}>
                    {/* Stepper line */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginRight: 16, width: 32, flexShrink: 0 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                        background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(139,92,246,0.2))',
                        border: '1px solid rgba(59,130,246,0.35)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 800, color: '#93C5FD',
                      }}>
                        {i + 1}
                      </div>
                      {i < workflow.length - 1 && (
                        <div style={{ width: 1, flex: 1, minHeight: 20, background: 'rgba(59,130,246,0.2)', margin: '4px 0' }} />
                      )}
                    </div>
                    <div style={{ paddingBottom: i < workflow.length - 1 ? 20 : 0, paddingTop: 4 }}>
                      <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>
                        {step.replace(/^Step\s*\d+:\s*/i, '')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ARCHITECTURE TAB */}
        {activeTab === 'architecture' && (
          <div>
            {architectureNotes && (
              <div style={{
                padding: '16px 18px', borderRadius: 12,
                background: 'rgba(59,130,246,0.05)',
                border: '1px solid rgba(59,130,246,0.14)',
                marginBottom: 20,
              }}>
                <p style={{ fontSize: 11, color: '#93C5FD', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                  Architecture Notes · Groq Assessment
                </p>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                  {architectureNotes}
                </p>
              </div>
            )}
            {!architectureNotes && <EmptyState message="No architecture notes generated" />}
          </div>
        )}
      </div>
    </div>
  )
}

function InfoChip({ label, value, color }) {
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 10, maxWidth: 380,
      background: `${color}0A`, border: `1px solid ${color}20`,
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, color, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 4 }}>
        {label}
      </span>
      <span style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        {value}
      </span>
    </div>
  )
}

function EmptyState({ message }) {
  return (
    <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
      <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>—</div>
      <p style={{ fontSize: 13 }}>{message}</p>
    </div>
  )
}
