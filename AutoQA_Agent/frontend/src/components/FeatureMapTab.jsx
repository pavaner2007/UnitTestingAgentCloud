import { useState, useMemo } from 'react'
import { ChevronDown, ChevronRight, Search, CheckCircle, Code, Database, Globe, Settings, FileText, Key, Package, Layers } from 'lucide-react'

const FEATURE_ICONS = {
  'Authentication':           '🔐',
  'User Management':          '👥',
  'Payment & Billing':        '💳',
  'Notifications':            '🔔',
  'File Upload & Storage':    '📁',
  'Search':                   '🔍',
  'Analytics & Reporting':    '📊',
  'Admin Dashboard':          '🛡️',
  'AI / Machine Learning':    '🤖',
  'Inventory & Products':     '📦',
  'Reviews & Ratings':        '⭐',
  'Social & Community':       '🌐',
  'Scheduling & Events':      '📅',
}

const FEATURE_COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
  '#ef4444', '#06b6d4', '#84cc16', '#f97316',
  '#ec4899', '#6366f1', '#14b8a6', '#a855f7',
]

function ConfidenceMeter({ score }) {
  const pct = Math.round((score || 0) * 100)
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{ flex: 1, height: '4px', background: 'var(--bg-app)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ fontSize: '11px', fontWeight: 700, color, minWidth: '30px', textAlign: 'right' }}>{pct}%</span>
    </div>
  )
}

function ItemList({ items, emptyText = 'None detected', icon, color }) {
  if (!items || items.length === 0) {
    return <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>{emptyText}</span>
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
      {items.map((item, i) => (
        <span key={i} style={{
          fontSize: '11px', padding: '2px 8px', borderRadius: '12px',
          background: (color || '#3b82f6') + '18',
          color: color || '#60a5fa',
          border: `1px solid ${(color || '#3b82f6')}33`,
          fontFamily: 'monospace',
        }}>
          {icon && <span style={{ marginRight: '4px' }}>{icon}</span>}
          {String(item).split('/').pop()}
        </span>
      ))}
    </div>
  )
}

function MethodBadge({ api }) {
  const [method, ...pathParts] = api.split(' ')
  const path = pathParts.join(' ')
  const methodColors = {
    GET: '#22c55e', POST: '#3b82f6', PUT: '#f59e0b',
    DELETE: '#ef4444', PATCH: '#8b5cf6',
  }
  const c = methodColors[method] || '#6b7280'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '11px' }}>
      <span style={{
        fontWeight: 700, padding: '1px 6px', borderRadius: '4px',
        background: c + '22', color: c, border: `1px solid ${c}44`,
      }}>
        {method}
      </span>
      <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{path}</span>
    </span>
  )
}

function FeatureCard({ feature, colorAccent, index, isExpanded, onToggle }) {
  const icon = FEATURE_ICONS[feature.feature_name] || '🔷'
  const apiCount = feature.related_apis?.length || 0
  const fileCount = feature.implementation_files?.length || 0

  return (
    <div style={{
      background: 'var(--bg-card)', borderRadius: '14px',
      border: `1px solid ${isExpanded ? colorAccent + '55' : 'var(--border-subtle)'}`,
      overflow: 'hidden', transition: 'all 0.2s',
      boxShadow: isExpanded ? `0 0 0 1px ${colorAccent}33` : 'none',
    }}>
      {/* Card Header */}
      <div
        onClick={onToggle}
        style={{
          padding: '14px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '12px',
          background: isExpanded ? colorAccent + '11' : 'transparent',
          transition: 'background 0.2s',
        }}
      >
        <div style={{
          width: '40px', height: '40px', borderRadius: '10px', flexShrink: 0,
          background: colorAccent + '22', border: `1px solid ${colorAccent}33`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px',
        }}>
          {icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {feature.feature_name}
            </span>
            <CheckCircle size={13} style={{ color: colorAccent, flexShrink: 0 }} />
          </div>
          <ConfidenceMeter score={feature.confidence_score} />
          <div style={{ display: 'flex', gap: '12px', marginTop: '5px', fontSize: '11px', color: 'var(--text-muted)' }}>
            {apiCount > 0 && <span>🌐 {apiCount} API{apiCount !== 1 ? 's' : ''}</span>}
            {fileCount > 0 && <span>📄 {fileCount} file{fileCount !== 1 ? 's' : ''}</span>}
            {feature.related_env_vars?.length > 0 && <span>🔑 {feature.related_env_vars.length} env var{feature.related_env_vars.length !== 1 ? 's' : ''}</span>}
          </div>
        </div>
        <div style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div style={{ borderTop: `1px solid ${colorAccent}22`, padding: '16px' }}>
          {feature.description && (
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: '1.6' }}>
              {feature.description}
            </p>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            {[
              { label: 'Related APIs', items: feature.related_apis, icon: '🌐', color: '#3b82f6', render: 'api' },
              { label: 'Controllers', items: feature.related_controllers, icon: null, color: '#8b5cf6', render: 'list' },
              { label: 'Services', items: feature.related_services, icon: null, color: '#10b981', render: 'list' },
              { label: 'Models', items: feature.related_models, icon: null, color: '#f59e0b', render: 'list' },
              { label: 'DB Tables', items: feature.related_db_tables, icon: '🗄️', color: '#06b6d4', render: 'list' },
              { label: 'Env Variables', items: feature.related_env_vars, icon: '🔑', color: '#84cc16', render: 'list' },
              { label: 'Config Files', items: feature.related_config_files, icon: '⚙️', color: '#f97316', render: 'list' },
              { label: 'Dependencies', items: feature.dependencies, icon: null, color: '#ec4899', render: 'list' },
            ].map(section => (
              <div key={section.label}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
                  {section.label}
                </div>
                {section.render === 'api' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {section.items?.length ? section.items.slice(0, 5).map((api, i) => (
                      <MethodBadge key={i} api={api} />
                    )) : <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>None detected</span>}
                    {section.items?.length > 5 && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>+{section.items.length - 5} more</span>
                    )}
                  </div>
                ) : (
                  <ItemList items={section.items?.slice(0, 6)} color={section.color} />
                )}
              </div>
            ))}
          </div>

          {feature.implementation_files?.length > 0 && (
            <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
                Implementation Files
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {feature.implementation_files.slice(0, 10).map((f, i) => (
                  <span key={i} style={{
                    fontSize: '10px', padding: '2px 6px', fontFamily: 'monospace',
                    background: 'var(--bg-app)', color: 'var(--text-muted)',
                    border: '1px solid var(--border-subtle)', borderRadius: '4px',
                  }}>
                    {f.split('/').slice(-2).join('/')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function FeatureMapTab({ analysisId, report }) {
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  const featureMap = report?.feature_map
  const features = featureMap?.features || []
  const totalFeatures = featureMap?.total_features_detected || features.length

  const filteredFeatures = useMemo(() => {
    if (!searchQuery) return features
    const q = searchQuery.toLowerCase()
    return features.filter(f =>
      f.feature_name.toLowerCase().includes(q) ||
      f.description?.toLowerCase().includes(q)
    )
  }, [features, searchQuery])

  if (!featureMap || features.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '300px', gap: '12px' }}>
        <div style={{ fontSize: '48px' }}>🗺️</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '16px' }}>No feature map data available.</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Re-analyze the repository to generate the feature map.</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #0f4c2a, #166534)',
        borderRadius: '12px', padding: '16px 20px',
        border: '1px solid #15803d55',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
          <div style={{ fontSize: '32px' }}>🗺️</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '18px', fontWeight: 700, color: '#bbf7d0' }}>Feature Map</div>
            <div style={{ fontSize: '13px', color: '#86efac' }}>
              {featureMap.summary || `${totalFeatures} business features automatically detected`}
            </div>
          </div>
        </div>
        {/* Feature summary bubbles */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {features.map((f, i) => (
            <div
              key={f.feature_name}
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', borderRadius: '20px', cursor: 'pointer',
                background: (FEATURE_COLORS[i % FEATURE_COLORS.length]) + '22',
                border: `1px solid ${FEATURE_COLORS[i % FEATURE_COLORS.length]}44`,
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: '14px' }}>{FEATURE_ICONS[f.feature_name] || '🔷'}</span>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#bbf7d0' }}>{f.feature_name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Search */}
      <div style={{ position: 'relative' }}>
        <Search size={14} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search features…"
          style={{
            width: '100%', padding: '9px 12px 9px 34px', borderRadius: '10px', fontSize: '13px',
            background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Feature Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {filteredFeatures.map((feature, idx) => {
          const originalIdx = features.indexOf(feature)
          const colorAccent = FEATURE_COLORS[originalIdx % FEATURE_COLORS.length]
          return (
            <FeatureCard
              key={feature.feature_name}
              feature={feature}
              colorAccent={colorAccent}
              index={originalIdx}
              isExpanded={expandedIdx === originalIdx}
              onToggle={() => setExpandedIdx(expandedIdx === originalIdx ? null : originalIdx)}
            />
          )
        })}
      </div>

      {filteredFeatures.length === 0 && searchQuery && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px', fontSize: '13px' }}>
          No features match "{searchQuery}"
        </div>
      )}
    </div>
  )
}
