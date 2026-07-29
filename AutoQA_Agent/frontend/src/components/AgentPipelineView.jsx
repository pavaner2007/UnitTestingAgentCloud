import { useEffect, useRef } from 'react'

const STATUS_META = {
  queued:  { icon: '⏳', color: 'var(--text-muted)',   borderColor: 'rgba(255,255,255,0.06)', bg: 'rgba(255,255,255,0.02)', pulse: false },
  running: { icon: '⟳',  color: '#a5b4fc',             borderColor: 'rgba(99,102,241,0.5)',  bg: 'rgba(99,102,241,0.06)',  pulse: true  },
  done:    { icon: '✓',  color: 'var(--accent-teal)',  borderColor: 'rgba(20,210,160,0.4)',  bg: 'rgba(20,210,160,0.05)', pulse: false },
  failed:  { icon: '✗',  color: '#f87171',             borderColor: 'rgba(239,68,68,0.4)',   bg: 'rgba(239,68,68,0.05)',  pulse: false },
  skipped: { icon: '—',  color: 'var(--text-muted)',   borderColor: 'rgba(255,255,255,0.06)', bg: 'rgba(255,255,255,0.02)', pulse: false },
}

const NUMERIC_PREVIEW_RE = /^\d/

function AgentCard({ agent, index }) {
  const meta = STATUS_META[agent.status] || STATUS_META.queued
  const isNumericPreview = agent.preview && NUMERIC_PREVIEW_RE.test(agent.preview)

  return (
    <div
      style={{
        borderRadius: 10,
        border: `1px solid ${meta.borderColor}`,
        background: meta.bg,
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        transition: 'border-color 0.3s ease, background 0.3s ease',
        position: 'relative',
        overflow: 'hidden',
        // Use separate longhand animation properties — mixing the `animation`
        // shorthand with `animationDelay` causes a React style conflict warning.
        animationName: agent.status === 'done' ? 'fadeIn' : 'none',
        animationDuration: '0.4s',
        animationTimingFunction: 'ease',
        animationFillMode: 'both',
        animationDelay: `${index * 0.04}s`,
      }}
    >
      {/* Running pulse ring */}
      {meta.pulse && (
        <span style={{
          position: 'absolute',
          inset: -1,
          borderRadius: 10,
          border: '1px solid rgba(99,102,241,0.35)',
          animation: 'pipelinePulse 1.4s ease-in-out infinite',
          pointerEvents: 'none',
        }} />
      )}

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Status icon */}
        <span style={{
          fontSize: agent.status === 'running' ? 15 : 13,
          color: meta.color,
          flexShrink: 0,
          animation: agent.status === 'running' ? 'spin 0.8s linear infinite' : 'none',
          display: 'inline-block',
          lineHeight: 1,
        }}>
          {meta.icon}
        </span>

        {/* Stage name */}
        <span style={{
          fontSize: 12,
          fontWeight: agent.status === 'running' ? 700 : 600,
          color: agent.status === 'queued' ? 'var(--text-muted)' : 'var(--text-primary)',
          letterSpacing: '-0.01em',
          transition: 'color 0.3s ease',
          flex: 1,
        }}>
          {agent.name}
        </span>

        {/* Step number badge */}
        <span style={{
          fontSize: 9,
          fontWeight: 700,
          color: 'var(--text-muted)',
          letterSpacing: '0.06em',
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 4,
          padding: '1px 5px',
          flexShrink: 0,
        }}>
          {String(index + 1).padStart(2, '0')}
        </span>
      </div>

      {/* Preview text */}
      {agent.preview && (
        <span style={{
          fontSize: 11,
          color: meta.color,
          fontFamily: isNumericPreview ? "'Fira Code', 'Cascadia Code', monospace" : 'inherit',
          letterSpacing: isNumericPreview ? '0.02em' : 'normal',
          opacity: 0.85,
          paddingLeft: 22,
          lineHeight: 1.3,
        }}>
          {agent.preview}
        </span>
      )}

      {/* Running shimmer bar */}
      {agent.status === 'running' && (
        <div style={{
          position: 'absolute',
          bottom: 0, left: 0, right: 0,
          height: 2,
          background: 'linear-gradient(90deg, transparent 0%, rgba(99,102,241,0.6) 50%, transparent 100%)',
          animation: 'shimmer 1.5s ease-in-out infinite',
        }} />
      )}
    </div>
  )
}

export default function AgentPipelineView({ agents = [], repoUrl = '' }) {
  const total = agents.length
  const done  = agents.filter(a => a.status === 'done').length
  const failed = agents.filter(a => a.status === 'failed').length
  const running = agents.find(a => a.status === 'running')
  const progressPct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div style={{
      width: '100%',
      maxWidth: 820,
      margin: '0 auto',
      padding: '32px 24px 48px',
      animation: 'fadeIn 0.35s ease both',
    }}>

      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{
              fontSize: 18,
              fontWeight: 800,
              color: 'var(--text-primary)',
              letterSpacing: '-0.03em',
              margin: 0,
            }}>
              Analyzing repository
            </h2>
            {repoUrl && (
              <p style={{
                fontSize: 12,
                color: 'var(--text-muted)',
                fontFamily: "'Fira Code', monospace",
                margin: '4px 0 0',
              }}>
                {repoUrl.replace('https://github.com/', '')}
              </p>
            )}
          </div>

          {/* Counter badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 14px',
            background: failed > 0 ? 'rgba(239,68,68,0.08)' : 'rgba(20,210,160,0.08)',
            border: `1px solid ${failed > 0 ? 'rgba(239,68,68,0.25)' : 'rgba(20,210,160,0.2)'}`,
            borderRadius: 99,
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%',
              background: failed > 0 ? '#f87171' : 'var(--accent-teal)',
              animation: running ? 'pulseGlow 1.2s ease infinite' : 'none',
              display: 'inline-block',
              flexShrink: 0,
            }} />
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: failed > 0 ? '#f87171' : 'var(--accent-teal)',
              fontFamily: "'Fira Code', monospace",
            }}>
              {done}/{total} agents complete
              {failed > 0 && ` · ${failed} failed`}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{
          height: 4, borderRadius: 4,
          background: 'rgba(255,255,255,0.06)',
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${progressPct}%`,
            background: failed > 0
              ? 'linear-gradient(90deg, var(--accent-teal), #f87171)'
              : 'linear-gradient(90deg, var(--accent-teal), #60a5fa)',
            borderRadius: 4,
            transition: 'width 0.5s ease',
          }} />
        </div>

        {/* Currently running label */}
        {running && (
          <p style={{
            fontSize: 11, color: '#a5b4fc',
            margin: 0, display: 'flex', alignItems: 'center', gap: 6,
            letterSpacing: '0.04em',
          }}>
            <span style={{
              display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
              background: '#a5b4fc',
              animation: 'pulseGlow 1s ease infinite',
            }} />
            Running: {running.name}…
          </p>
        )}
      </div>

      {/* Agent grid — 3 columns */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10,
      }}>
        {agents.map((agent, i) => (
          <AgentCard key={agent.name} agent={agent} index={i} />
        ))}
      </div>
    </div>
  )
}
