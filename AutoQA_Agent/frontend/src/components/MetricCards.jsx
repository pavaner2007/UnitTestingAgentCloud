import { FileCode2, Route, Layers, Target, FolderGit2, Download } from 'lucide-react'

function getConfidenceColor(score) {
  if (score == null) return '#64748B'
  if (score >= 80) return '#10B981'
  if (score >= 60) return '#F59E0B'
  return '#EF4444'
}

function MetricCard({ icon: Icon, value, label, accent, delay = 0 }) {
  const isNumber = typeof value === 'number'

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: '22px 24px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'transform 0.2s, box-shadow 0.2s, border-color 0.2s',
        animation: `fadeSlideUp 0.5s ease ${delay}ms both`,
        cursor: 'default',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-3px)'
        e.currentTarget.style.boxShadow = `0 8px 32px ${accent}20`
        e.currentTarget.style.borderColor = `${accent}30`
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = ''
        e.currentTarget.style.boxShadow = ''
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      {/* Background glow blob */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 80% 60% at 10% 20%, ${accent}09 0%, transparent 70%)`,
      }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10,
          background: `${accent}18`, border: `1px solid ${accent}28`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <Icon size={16} color={accent} />
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {label}
        </span>
      </div>

      <div style={{
        fontSize: isNumber ? 34 : 20,
        fontWeight: 800,
        color: 'var(--text-primary)',
        letterSpacing: isNumber ? '-0.03em' : '-0.01em',
        lineHeight: 1.1,
        wordBreak: 'break-all',
        fontFamily: isNumber ? 'Inter, sans-serif' : 'JetBrains Mono, monospace',
      }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

function ConfidenceCard({ report, delay = 0, onDownload, pdfLoading }) {
  const score = report?.confidence_score
  const color = getConfidenceColor(score)
  const sublabel = score >= 80 ? 'High Confidence Analysis' : score >= 60 ? 'Moderate Confidence' : 'Low Confidence'
  const badge = score >= 80 ? 'High' : score >= 60 ? 'Medium' : 'Low'

  const scorePct = score != null ? Math.min(100, Math.max(0, score)) : 0

  const numFiles = report?.number_of_files ?? 0
  const numApis = report?.number_of_apis_discovered ?? 0

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: '22px 24px',
        position: 'relative',
        overflow: 'hidden',
        transition: 'transform 0.2s, box-shadow 0.2s, border-color 0.2s',
        animation: `fadeSlideUp 0.5s ease ${delay}ms both`,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: 16,
        gridColumn: 'span 2',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'translateY(-3px)'
        e.currentTarget.style.boxShadow = `0 8px 32px ${color}25`
        e.currentTarget.style.borderColor = `${color}30`
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = ''
        e.currentTarget.style.boxShadow = ''
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      {/* Background glow */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `radial-gradient(ellipse 80% 60% at 50% 0%, ${color}0A 0%, transparent 70%)`,
      }} />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10, flexShrink: 0,
            background: `${color}18`, border: `1px solid ${color}28`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Target size={16} color={color} />
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Confidence Rating
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
              {sublabel}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24, fontWeight: 900, color, letterSpacing: '-0.02em', lineHeight: 1 }}>
            {score != null ? `${Math.round(score)}%` : '—'}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 99,
            background: `${color}18`, border: `1px solid ${color}30`, color,
            letterSpacing: '0.04em',
          }}>
            {badge}
          </span>
        </div>
      </div>

      {/* Horizontal Calibration Bar */}
      <div>
        <div style={{
          position: 'relative',
          height: 10,
          borderRadius: 99,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.08)',
          overflow: 'visible',
          marginTop: 6,
        }}>
          {/* Gradient zones track */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: 99,
            background: 'linear-gradient(90deg, #EF4444 0%, #F59E0B 50%, #10B981 100%)',
            opacity: 0.85,
          }} />

          {/* Pointer Marker */}
          <div style={{
            position: 'absolute',
            top: -4,
            left: `${scorePct}%`,
            transform: 'translateX(-50%)',
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: '#FFF',
            border: `3px solid ${color}`,
            boxShadow: `0 0 10px ${color}`,
            transition: 'left 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
          }} />
        </div>

        {/* Zone Markers */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>
          <span>0% Low</span>
          <span>50% Medium</span>
          <span>80% High</span>
          <span>100%</span>
        </div>
      </div>

      {/* Footer annotation line + Download button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 4 }}>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          Based on <span className="mono-code">{numFiles} files</span> analyzed and <span className="mono-code">{numApis} APIs</span> verified.
        </div>

        {onDownload && (
          <button
            onClick={onDownload}
            disabled={pdfLoading}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
              color: '#fff', border: 'none', borderRadius: 10,
              padding: '8px 14px', fontSize: 12, fontWeight: 700,
              cursor: pdfLoading ? 'not-allowed' : 'pointer',
              opacity: pdfLoading ? 0.7 : 1,
              fontFamily: 'Inter, sans-serif',
              transition: 'opacity 0.2s, transform 0.15s, box-shadow 0.15s',
              letterSpacing: '-0.01em',
              boxShadow: '0 2px 14px rgba(59,130,246,0.4)',
              flexShrink: 0,
            }}
            onMouseEnter={e => { if (!pdfLoading) { e.currentTarget.style.transform = 'scale(1.02)'; e.currentTarget.style.boxShadow = '0 4px 20px rgba(59,130,246,0.55)' } }}
            onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '0 2px 14px rgba(59,130,246,0.4)' }}
          >
            <Download size={13} />
            {pdfLoading ? 'Generating…' : 'Download PDF'}
          </button>
        )}
      </div>
    </div>
  )
}

export default function MetricCards({ report, onDownload, pdfLoading }) {
  if (!report) return null

  const techCount = Object.values(report.technology_stack || {})
    .flat().filter(Boolean).length

  const cards = [
    {
      icon: FolderGit2,
      value: report.repository_name,
      label: 'Repository',
      accent: '#6366F1',
    },
    {
      icon: FileCode2,
      value: report.number_of_files,
      label: 'Files Scanned',
      accent: '#06B6D4',
    },
    {
      icon: Route,
      value: report.number_of_apis_discovered,
      label: 'APIs Found',
      accent: '#10B981',
    },
    {
      icon: Layers,
      value: techCount,
      label: 'Technologies',
      accent: '#A78BFA',
    },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 24 }}>
      {cards.map((c, i) => (
        <MetricCard key={c.label} {...c} delay={i * 60} />
      ))}
      <ConfidenceCard
        report={report}
        delay={cards.length * 60}
        onDownload={onDownload}
        pdfLoading={pdfLoading}
      />
    </div>
  )
}
