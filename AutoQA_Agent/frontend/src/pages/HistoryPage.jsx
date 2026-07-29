import { useEffect, useState } from 'react'
import { getAnalyses, getAnalysis } from '../api/client'
import { Clock, FolderGit2, Target, RefreshCw, ArrowRight } from 'lucide-react'

function getConfidenceColor(score) {
  if (score == null) return '#64748B'
  if (score >= 80)   return '#10B981'
  if (score >= 60)   return '#F59E0B'
  return '#EF4444'
}

function SkeletonCard() {
  return (
    <div className="skeleton" style={{ height: 160, borderRadius: 14 }} />
  )
}

export default function HistoryPage({ onSelectReport }) {
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingId, setLoadingId] = useState(null)

  async function fetchHistory() {
    setLoading(true)
    const data = await getAnalyses()
    setAnalyses(data)
    setLoading(false)
  }

  useEffect(() => { fetchHistory() }, [])

  async function handleOpen(id) {
    setLoadingId(id)
    try {
      const data = await getAnalysis(id)
      onSelectReport(data.report || data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div style={{
      padding: '40px 36px',
      animation: 'fadeSlideUp 0.4s ease both',
      minHeight: '100vh',
      background: 'var(--bg-app)',
    }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 32, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Clock size={16} color="var(--text-muted)" />
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Analysis History
            </span>
          </div>
          <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1 }}>
            Previous Analyses
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 6 }}>
            {analyses.length > 0 ? `${analyses.length} repositor${analyses.length === 1 ? 'y' : 'ies'} analyzed` : 'No previous analyses yet'}
          </p>
        </div>
        <button
          onClick={fetchHistory}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '9px 16px', borderRadius: 10,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--border)',
            color: 'var(--text-secondary)', fontSize: 13, fontWeight: 500,
            cursor: 'pointer', fontFamily: 'Inter, sans-serif',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
            e.currentTarget.style.color = 'var(--text-primary)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
            e.currentTarget.style.color = 'var(--text-secondary)'
          }}
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
          {[1,2,3,4].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && analyses.length === 0 && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '80px 24px', textAlign: 'center',
          border: '1px dashed var(--border)', borderRadius: 18,
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: 'rgba(255,255,255,0.04)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, fontSize: 28,
          }}>
            📂
          </div>
          <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 8 }}>No analyses yet</h3>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 320, lineHeight: 1.65 }}>
            Analyze your first GitHub repository from the Dashboard to see it here.
          </p>
        </div>
      )}

      {/* Analysis cards grid */}
      {!loading && analyses.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
          {analyses.map((item, i) => {
            const conf = item.confidence_score ?? item.report?.confidence_score
            const confColor = getConfidenceColor(conf)
            const stack = item.technology_stack || item.report?.technology_stack || {}
            // Stack values may be arrays OR objects — extract string names from both
            const extractTech = (val) => {
              if (Array.isArray(val)) return val.filter(v => typeof v === 'string')
              if (val && typeof val === 'object') return Object.keys(val)
              if (typeof val === 'string') return [val]
              return []
            }
            const allTechFull = Object.values(stack).flatMap(extractTech).filter(Boolean)
            const allTech = allTechFull.slice(0, 5)
            const extraCount = allTechFull.length - 5
            const createdAt = item.created_at
              ? new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
              : '—'

            return (
              <div
                key={item.analysis_id || item.id || i}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 14, padding: '20px',
                  transition: 'all 0.2s', cursor: 'pointer',
                  animation: `fadeSlideUp 0.4s ease ${i * 50}ms both`,
                  position: 'relative', overflow: 'hidden',
                }}
                onClick={() => handleOpen(item.analysis_id || item.id)}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'rgba(59,130,246,0.25)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 8px 28px rgba(0,0,0,0.4)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.transform = ''
                  e.currentTarget.style.boxShadow = ''
                }}
              >
                {/* Glow blob */}
                <div style={{
                  position: 'absolute', inset: 0, pointerEvents: 'none',
                  background: 'radial-gradient(ellipse 80% 50% at 10% 10%, rgba(59,130,246,0.05) 0%, transparent 60%)',
                }} />

                {/* Repo name */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 14 }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                    background: 'rgba(99,102,241,0.12)',
                    border: '1px solid rgba(99,102,241,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <FolderGit2 size={13} color="#A5B4FC" />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontSize: 14, fontWeight: 700, color: 'var(--text-primary)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      letterSpacing: '-0.01em',
                    }}>
                      {item.repository_name || '—'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{createdAt}</div>
                  </div>
                </div>

                {/* Tech chips */}
                {allTech.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 14 }}>
                    {allTech.map((t, ti) => (
                      <span key={`${i}-${ti}-${t}`} style={{
                        fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
                        background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)',
                        color: 'var(--text-secondary)',
                      }}>{String(t)}</span>
                    ))}
                    {extraCount > 0 && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
                        background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)',
                        color: 'var(--text-muted)',
                      }}>
                        +{extraCount} more
                      </span>
                    )}
                  </div>
                )}

                {/* Footer */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  {conf != null ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <Target size={11} color={confColor} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: confColor }}>
                        {Math.round(conf)}%
                      </span>
                    </div>
                  ) : <div />}
                  <span style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    fontSize: 11, color: '#3B82F6', fontWeight: 600,
                    opacity: loadingId === (item.analysis_id || item.id) ? 0.6 : 1,
                  }}>
                    {loadingId === (item.analysis_id || item.id) ? 'Loading…' : <>View <ArrowRight size={10} /></>}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
