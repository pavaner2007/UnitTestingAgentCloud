/**
 * ArchitectureTab — Logical Layer Diagram
 *
 * Shows the project as stacked horizontal swim-lanes (not a per-file import graph).
 * Files are bucketed into layers by directory name / filename heuristics:
 *   API / Routes / Controllers
 *   Business Logic / Services
 *   Data / Models / Database
 *   Infrastructure / Config
 *   Frontend / UI
 *   Tests
 *   Other
 *
 * Each swim-lane lists its files as pill chips. An SVG connector line with a
 * down-arrow runs between adjacent lanes to show the call flow direction.
 * This is visually and structurally distinct from DependencyGraphPanel.
 */

const LAYERS = [
  {
    id: 'frontend',
    label: 'Frontend / UI',
    color: '#7c3aed',
    bg: 'rgba(124,58,237,0.08)',
    border: 'rgba(124,58,237,0.3)',
    icon: '⬡',
    dirPatterns: ['frontend', 'client', 'web', 'ui', 'pages', 'views', 'components', 'src'],
    filePatterns: ['.jsx', '.tsx', '.vue', '.svelte', '.html', '.css'],
  },
  {
    id: 'api',
    label: 'API / Routes',
    color: '#0891b2',
    bg: 'rgba(8,145,178,0.08)',
    border: 'rgba(8,145,178,0.3)',
    icon: '⇌',
    dirPatterns: ['routes', 'route', 'controllers', 'controller', 'api', 'handlers', 'handler', 'endpoints', 'views'],
    filePatterns: ['route', 'router', 'controller', 'handler', 'endpoint', 'server'],
  },
  {
    id: 'services',
    label: 'Business Logic / Services',
    color: '#14D2A0',
    bg: 'rgba(20,210,160,0.08)',
    border: 'rgba(20,210,160,0.3)',
    icon: '◈',
    dirPatterns: ['services', 'service', 'domain', 'core', 'logic', 'use_cases', 'usecases', 'business'],
    filePatterns: ['service', 'manager', 'processor', 'workflow', 'usecase'],
  },
  {
    id: 'data',
    label: 'Data / Models / DB',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.3)',
    icon: '⬡',
    dirPatterns: ['models', 'model', 'db', 'database', 'repositories', 'repository', 'schemas', 'schema', 'migrations', 'entities'],
    filePatterns: ['model', 'schema', 'entity', 'migration', 'repository', 'store', '.sql', 'db', 'orm'],
  },
  {
    id: 'config',
    label: 'Config / Infrastructure',
    color: '#94a3b8',
    bg: 'rgba(148,163,184,0.07)',
    border: 'rgba(148,163,184,0.25)',
    icon: '⚙',
    dirPatterns: ['config', 'conf', 'settings', 'infra', 'infrastructure', 'deploy', 'scripts', 'middleware', 'auth'],
    filePatterns: ['config', 'settings', 'middleware', 'auth', '.env', 'dockerfile', 'makefile', 'docker'],
  },
  {
    id: 'tests',
    label: 'Tests',
    color: '#a78bfa',
    bg: 'rgba(167,139,250,0.07)',
    border: 'rgba(167,139,250,0.25)',
    icon: '✓',
    dirPatterns: ['tests', 'test', '__tests__', 'spec', 'e2e'],
    filePatterns: ['test_', '.test.', '.spec.', '_test.'],
  },
]

/** Classify a file path to a layer id */
function classifyFile(filePath) {
  const parts = filePath.toLowerCase().replace(/\\/g, '/').split('/')
  const filename = parts[parts.length - 1]
  const dirs = parts.slice(0, -1)

  // Test files — check first to avoid misclassifying as services
  const testLayer = LAYERS.find(l => l.id === 'tests')
  if (
    dirs.some(d => testLayer.dirPatterns.includes(d)) ||
    testLayer.filePatterns.some(p => filename.includes(p))
  ) return 'tests'

  // Check directory match (strongest signal)
  for (const layer of LAYERS) {
    if (layer.id === 'tests') continue
    if (dirs.some(d => layer.dirPatterns.includes(d))) return layer.id
  }

  // Check filename patterns
  for (const layer of LAYERS) {
    if (layer.id === 'tests') continue
    if (layer.filePatterns.some(p => filename.includes(p) || filename.endsWith(p))) return layer.id
  }

  return null  // uncategorized
}

/** Short display label: last 2 path segments */
function shortLabel(filePath) {
  const parts = filePath.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
}

function LayerChip({ label, color, bg, border }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 9px',
      borderRadius: 6,
      background: bg,
      border: `1px solid ${border}`,
      color,
      fontSize: 10,
      fontFamily: 'JetBrains Mono, monospace',
      fontWeight: 500,
      letterSpacing: '-0.01em',
      whiteSpace: 'nowrap',
      maxWidth: 220,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      title: label,
    }}>
      {label}
    </span>
  )
}

function DownArrow({ color }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '4px 0', gap: 1,
    }}>
      <div style={{ width: 1, height: 18, background: color, opacity: 0.4 }} />
      <svg width={10} height={8} viewBox="0 0 10 8">
        <polygon points="5,8 0,0 10,0" fill={color} opacity={0.6} />
      </svg>
    </div>
  )
}

export default function ArchitectureTab({ report }) {
  const overview =
    report?.ai_explanation?.project_overview ||
    report?.architecture_notes ||
    null

  // ── Collect all analyzed + dep-graph files ──────────────────────────────
  const allFiles = (() => {
    const set = new Set()
    // From code_insights
    for (const f of (report?.code_insights?.analyzed_files || [])) set.add(f)
    // From dep graph nodes — same file may appear with a different path prefix
    // (e.g. "frontend/src/App.jsx" vs "AutoQA_Agent/frontend/src/App.jsx").
    // We already use a Set for exact-path dedup; cross-source path normalization
    // is handled at the bucket level below.
    for (const n of (report?.dependency_graph?.nodes || [])) set.add(n.file)
    for (const n of (report?.code_insights?.dependency_graph?.nodes || [])) set.add(n.file)
    return [...set]
  })()

  // ── Bucket files into layers ────────────────────────────────────────────
  const buckets = {}
  for (const layer of LAYERS) buckets[layer.id] = []
  const uncategorized = []

  for (const file of allFiles) {
    const layerId = classifyFile(file)
    if (layerId && buckets[layerId]) {
      buckets[layerId].push(file)
    } else {
      uncategorized.push(file)
    }
  }

  // Deduplicate each bucket by its display label (last 2 path segments).
  // This removes duplicates that survive the Set because the same physical
  // file arrived from two sources under different path prefixes.
  for (const layer of LAYERS) {
    const seen = new Set()
    buckets[layer.id] = buckets[layer.id].filter(file => {
      const label = shortLabel(file)
      if (seen.has(label)) return false
      seen.add(label)
      return true
    })
  }
  // Also deduplicate uncategorized
  const ucSeen = new Set()
  const uncategorizedDeduped = uncategorized.filter(file => {
    const label = shortLabel(file)
    if (ucSeen.has(label)) return false
    ucSeen.add(label)
    return true
  })


  // ── Tech stack facts from report ────────────────────────────────────────
  // Only include layers that have files (after dedup)
  const activeLayers = LAYERS.filter(l => buckets[l.id].length > 0)
  const hasData = activeLayers.length > 0 || allFiles.length > 0

  const tech = report?.technology_stack || {}
  const techItems = [
    ...(tech.frontend || []),
    ...(tech.backend || []),
    ...(tech.databases || []),
    ...(tech.frameworks || []),
    ...(tech.languages || []),
  ].filter((v, i, a) => v && a.indexOf(v) === i).slice(0, 12)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeSlideUp 0.45s ease both' }}>

      {/* ── OVERVIEW ── */}
      {overview && (
        <div style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 14, padding: '22px 26px',
        }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
            color: 'var(--accent-teal)', textTransform: 'uppercase', marginBottom: 10,
          }}>
            PROJECT OVERVIEW
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            {overview}
          </p>
        </div>
      )}

      {/* ── TECH STACK PILLS ── */}
      {techItems.length > 0 && (
        <div style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 14, padding: '18px 22px',
        }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
            color: 'var(--accent-teal)', textTransform: 'uppercase', marginBottom: 12,
          }}>
            TECH STACK
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {techItems.map(t => (
              <span key={t} style={{
                padding: '4px 11px', borderRadius: 6,
                background: 'rgba(20,210,160,0.07)',
                border: '1px solid rgba(20,210,160,0.2)',
                color: 'var(--accent-teal)',
                fontSize: 11, fontWeight: 600, letterSpacing: '0.02em',
              }}>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── LOGICAL LAYER DIAGRAM ── */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 22px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-teal)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            LOGICAL ARCHITECTURE
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Grouped by role — not by import
          </span>
        </div>

        <div style={{ padding: '28px 32px' }}>
          {!hasData ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
              <p style={{ fontSize: 14, fontWeight: 600 }}>No file data available for architecture diagram.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
              {activeLayers.map((layer, idx) => {
                const files = buckets[layer.id]
                const MAX_VISIBLE = 18
                const shown = files.slice(0, MAX_VISIBLE)
                const overflow = files.length - MAX_VISIBLE

                return (
                  <div key={layer.id} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    {/* Lane card */}
                    <div style={{
                      width: '100%',
                      background: layer.bg,
                      border: `1px solid ${layer.border}`,
                      borderRadius: 12,
                      padding: '16px 20px',
                    }}>
                      {/* Lane header */}
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
                      }}>
                        <span style={{
                          fontSize: 16, width: 28, height: 28,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: 'rgba(0,0,0,0.2)', borderRadius: 6,
                          color: layer.color,
                        }}>
                          {layer.icon}
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: layer.color, letterSpacing: '0.04em' }}>
                          {layer.label}
                        </span>
                        <span style={{
                          marginLeft: 'auto',
                          fontSize: 10, fontWeight: 600,
                          color: layer.color, opacity: 0.7,
                          background: 'rgba(0,0,0,0.15)',
                          padding: '2px 7px', borderRadius: 4,
                        }}>
                          {files.length} file{files.length !== 1 ? 's' : ''}
                        </span>
                      </div>

                      {/* File chips */}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {shown.map(f => (
                          <LayerChip key={f} label={shortLabel(f)} color={layer.color} bg={'rgba(0,0,0,0.18)'} border={layer.border} />
                        ))}
                        {overflow > 0 && (
                          <span style={{
                            padding: '3px 9px', borderRadius: 6,
                            background: 'rgba(0,0,0,0.15)', border: `1px solid ${layer.border}`,
                            color: layer.color, fontSize: 10, fontWeight: 600, opacity: 0.7,
                          }}>
                            +{overflow} more
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Connector arrow between layers */}
                    {idx < activeLayers.length - 1 && (
                      <DownArrow color={activeLayers[idx + 1].color} />
                    )}
                  </div>
                )
              })}

              {/* Uncategorized overflow */}
              {uncategorizedDeduped.length > 0 && (
                <div style={{ marginTop: 16, width: '100%', opacity: 0.55 }}>
                  <div style={{
                    fontSize: 10, color: 'var(--text-muted)', fontWeight: 600,
                    letterSpacing: '0.08em', marginBottom: 8, textTransform: 'uppercase',
                  }}>
                    OTHER ({uncategorizedDeduped.length})
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {uncategorizedDeduped.slice(0, 12).map(f => (
                      <LayerChip
                        key={f} label={shortLabel(f)}
                        color="var(--text-muted)"
                        bg="rgba(0,0,0,0.1)"
                        border="var(--border)"
                      />
                    ))}
                    {uncategorizedDeduped.length > 12 && (
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', padding: '3px 9px' }}>
                        +{uncategorizedDeduped.length - 12} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── API INVENTORY ── */}
      {(report?.api_inventory || []).length > 0 && (
        <div style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: 14, overflow: 'hidden',
        }}>
          <div style={{ padding: '14px 22px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-teal)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              API ENDPOINTS · {report.api_inventory.length} ROUTES
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
                  {['METHOD', 'PATH', 'FILE', 'FRAMEWORK'].map(h => (
                    <th key={h} style={{
                      padding: '9px 18px', textAlign: 'left',
                      fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                      letterSpacing: '0.1em', borderBottom: '1px solid var(--border)',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(report.api_inventory || []).slice(0, 30).map((ep, i) => {
                  const methodColors = {
                    GET: '#10b981', POST: '#3b82f6', PUT: '#f59e0b',
                    PATCH: '#8b5cf6', DELETE: '#ef4444',
                  }
                  const mc = methodColors[ep.method?.toUpperCase()] || 'var(--text-muted)'
                  return (
                    <tr
                      key={i}
                      style={{ borderBottom: '1px solid var(--border-soft)', transition: 'background 0.1s' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '9px 18px' }}>
                        <span style={{
                          fontSize: 10, fontWeight: 800, padding: '2px 7px', borderRadius: 4,
                          background: mc + '18', color: mc, border: `1px solid ${mc}40`,
                          letterSpacing: '0.04em',
                        }}>
                          {ep.method?.toUpperCase()}
                        </span>
                      </td>
                      <td style={{ padding: '9px 18px' }}>
                        <span className="mono-code" style={{ fontSize: 11, color: 'var(--text-primary)' }}>{ep.path}</span>
                      </td>
                      <td style={{ padding: '9px 18px' }}>
                        <span className="mono-code" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{ep.file}</span>
                      </td>
                      <td style={{ padding: '9px 18px', color: 'var(--text-secondary)', fontSize: 11 }}>
                        {ep.framework}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
