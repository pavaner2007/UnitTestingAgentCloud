import { Cpu } from 'lucide-react'

const GROUP_CONFIG = {
  frontend:   { label: 'Frontend',   color: '#6366F1' },
  backend:    { label: 'Backend',    color: '#06B6D4' },
  languages:  { label: 'Languages',  color: '#10B981' },
  databases:  { label: 'Databases',  color: '#F59E0B' },
  frameworks: { label: 'Frameworks', color: '#A78BFA' },
}

function TechItem({ name, color }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 10px', borderRadius: 6,
      background: 'rgba(255, 255, 255, 0.03)',
      border: '1px solid rgba(255, 255, 255, 0.07)',
      borderLeft: `3px solid ${color}`,
      fontSize: 12, fontWeight: 600,
      color: 'var(--text-primary)',
      transition: 'all 0.15s',
      cursor: 'default',
    }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'
        e.currentTarget.style.transform = ''
      }}
    >
      <span className="mono-code" style={{ padding: 0, border: 'none', background: 'transparent', color: 'var(--text-primary)', fontSize: 12 }}>
        {name}
      </span>
    </div>
  )
}

function TechGroup({ groupKey, items }) {
  const cfg = GROUP_CONFIG[groupKey]
  if (!cfg || !items || items.length === 0) return null
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {cfg.label}
        </span>
        <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${cfg.color}25, transparent)` }} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {items.map(item => (
          <TechItem key={item} name={item} color={cfg.color} />
        ))}
      </div>
    </div>
  )
}

export default function TechStackPanel({ stack, architectureNotes }) {
  if (!stack) return null

  const hasAny = Object.values(stack).some(arr => arr?.length > 0)
  if (!hasAny) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.25s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'linear-gradient(90deg, rgba(6,182,212,0.04) 0%, transparent 60%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'rgba(6,182,212,0.12)',
            border: '1px solid rgba(6,182,212,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Cpu size={16} color="#67E8F9" />
          </div>
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>Technology Stack</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              Deterministic detection from dependency files
            </p>
          </div>
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '3px 9px', borderRadius: 99,
          background: 'rgba(16,185,129,0.1)', color: '#6EE7B7',
          border: '1px solid rgba(16,185,129,0.2)', letterSpacing: '0.04em',
        }}>
          DETERMINISTIC
        </span>
      </div>

      {/* Groups */}
      <div style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
        {Object.keys(GROUP_CONFIG).map(key => (
          <TechGroup key={key} groupKey={key} items={stack[key]} />
        ))}
      </div>

      {/* Architecture notes */}
      {architectureNotes && (
        <div style={{
          margin: '0 24px 20px',
          padding: '14px 16px', borderRadius: 12,
          background: 'linear-gradient(135deg, rgba(59,130,246,0.06), rgba(139,92,246,0.05))',
          border: '1px solid rgba(59,130,246,0.15)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#93C5FD', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Architecture Notes
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>· Grounded by Ollama + Groq</span>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{architectureNotes}</p>
        </div>
      )}
    </div>
  )
}
