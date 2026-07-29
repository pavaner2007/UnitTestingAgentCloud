import { useState, useMemo } from 'react'
import { Search, Route } from 'lucide-react'

const METHOD_STYLES = {
  GET:    { bg: 'rgba(16,185,129,0.12)', color: '#34D399', border: 'rgba(16,185,129,0.25)' },
  POST:   { bg: 'rgba(245,158,11,0.12)', color: '#FCD34D', border: 'rgba(245,158,11,0.25)' },
  PUT:    { bg: 'rgba(59,130,246,0.12)', color: '#60A5FA', border: 'rgba(59,130,246,0.25)' },
  PATCH:  { bg: 'rgba(139,92,246,0.12)', color: '#C4B5FD', border: 'rgba(139,92,246,0.25)' },
  DELETE: { bg: 'rgba(239,68,68,0.12)',  color: '#F87171', border: 'rgba(239,68,68,0.25)' },
}

const FILTERS = ['ALL', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE']

function MethodBadge({ method }) {
  const m = method?.toUpperCase() || ''
  const s = METHOD_STYLES[m] || { bg: 'rgba(148,163,184,0.1)', color: '#94A3B8', border: 'rgba(148,163,184,0.2)' }
  return (
    <span style={{
      fontSize: 10, fontWeight: 800, padding: '3px 8px', borderRadius: 5,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.06em',
      display: 'inline-block',
    }}>
      {m}
    </span>
  )
}

export default function ApiTable({ endpoints }) {
  const list = endpoints || []
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('ALL')

  const filtered = useMemo(() => {
    return list.filter(ep => {
      const matchMethod = filter === 'ALL' || ep.method?.toUpperCase() === filter
      const q = query.toLowerCase()
      const matchQuery = !q
        || ep.path?.toLowerCase().includes(q)
        || ep.file?.toLowerCase().includes(q)
        || ep.framework?.toLowerCase().includes(q)
      return matchMethod && matchQuery
    })
  }, [list, query, filter])

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.35s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
        background: 'linear-gradient(90deg, rgba(16,185,129,0.03) 0%, transparent 60%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'rgba(16,185,129,0.1)',
            border: '1px solid rgba(16,185,129,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Route size={16} color="#6EE7B7" />
          </div>
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>API Inventory</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              AST-based discovery · {list.length} endpoint{list.length !== 1 ? 's' : ''} found
            </p>
          </div>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 99,
          background: 'rgba(6,182,212,0.1)', color: '#67E8F9',
          border: '1px solid rgba(6,182,212,0.2)',
        }}>
          {filtered.length} shown
        </span>
      </div>

      {list.length > 0 && (
        <>
          {/* Controls */}
          <div style={{
            padding: '12px 24px', borderBottom: '1px solid var(--border)',
            display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
            background: 'rgba(255,255,255,0.01)',
          }}>
            {/* Search */}
            <div style={{ position: 'relative', flex: 1, minWidth: 180 }}>
              <Search size={13} style={{
                position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
                color: 'var(--text-muted)', pointerEvents: 'none',
              }} />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search path, file, framework…"
                style={{
                  width: '100%', paddingLeft: 32, paddingRight: 12,
                  paddingTop: 8, paddingBottom: 8,
                  background: 'rgba(11,16,32,0.6)',
                  border: '1px solid var(--border)',
                  borderRadius: 8, color: 'var(--text-primary)',
                  fontSize: 12, outline: 'none', fontFamily: 'Inter, sans-serif',
                  transition: 'border-color 0.15s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(59,130,246,0.4)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'}
              />
            </div>

            {/* Method filters */}
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {FILTERS.map(m => {
                const isActive = filter === m
                const s = METHOD_STYLES[m]
                return (
                  <button
                    key={m}
                    onClick={() => setFilter(m)}
                    style={{
                      padding: '5px 11px', borderRadius: 6, border: '1px solid',
                      fontSize: 10, fontWeight: 800, cursor: 'pointer',
                      fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.05em',
                      transition: 'all 0.15s',
                      background: isActive
                        ? (s ? s.bg : 'rgba(59,130,246,0.15)')
                        : 'rgba(255,255,255,0.03)',
                      color: isActive
                        ? (s ? s.color : '#93C5FD')
                        : 'var(--text-muted)',
                      borderColor: isActive
                        ? (s ? s.border : 'rgba(59,130,246,0.3)')
                        : 'var(--border)',
                    }}
                  >
                    {m}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Table */}
          <div style={{ overflowX: 'auto' }}>
            {filtered.length === 0 ? (
              <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.4 }}>🔍</div>
                <p style={{ fontSize: 13 }}>No endpoints match your filter</p>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'rgba(11,16,32,0.4)' }}>
                    {['Method', 'Path', 'Framework', 'File', 'Line'].map(h => (
                      <th key={h} style={{
                        padding: '10px 16px', textAlign: 'left',
                        fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                        textTransform: 'uppercase', letterSpacing: '0.08em',
                        borderBottom: '1px solid var(--border)',
                        whiteSpace: 'nowrap',
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((ep, i) => (
                    <tr
                      key={`${ep.method}-${ep.path}-${i}`}
                      style={{
                        borderBottom: '1px solid var(--border-soft)',
                        background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.012)',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.04)'}
                      onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.012)'}
                    >
                      <td style={{ padding: '11px 16px' }}>
                        <MethodBadge method={ep.method} />
                      </td>
                      <td style={{ padding: '11px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: 'var(--text-primary)', fontWeight: 500 }}>
                        <span className="mono-code" style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                          {ep.path}
                        </span>
                      </td>
                      <td style={{ padding: '11px 16px', color: 'var(--text-secondary)', fontSize: 12 }}>
                        {ep.framework}
                      </td>
                      <td style={{
                        padding: '11px 16px', color: 'var(--text-muted)', fontSize: 11,
                        fontFamily: 'JetBrains Mono, monospace',
                        maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        <span className="mono-code" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {ep.file}
                        </span>
                      </td>
                      <td style={{ padding: '11px 16px', color: 'var(--text-muted)', textAlign: 'center', fontSize: 12 }}>
                        <span className="mono-code" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {ep.line_number || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {list.length === 0 && (
        <div style={{ padding: '56px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 40, marginBottom: 10, opacity: 0.35 }}>🔌</div>
          <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>No API endpoints discovered</p>
          <p style={{ fontSize: 12 }}>AST parsing found no Express, FastAPI, or Flask routes</p>
        </div>
      )}
    </div>
  )
}
