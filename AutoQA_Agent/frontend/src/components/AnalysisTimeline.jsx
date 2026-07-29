import { GitBranch, ScanSearch, Route, Sparkles, FileText, Check } from 'lucide-react'

const STEPS = [
  { icon: GitBranch,   label: 'Repository Cloned',   key: 'clone' },
  { icon: ScanSearch,  label: 'Tech Detected',        key: 'tech' },
  { icon: Route,       label: 'APIs Discovered',      key: 'apis' },
  { icon: Sparkles,    label: 'AI Analysis',          key: 'ai' },
  { icon: FileText,    label: 'Report Ready',         key: 'report' },
]

export default function AnalysisTimeline({ visible }) {
  if (!visible) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 16,
      padding: '20px 28px',
      marginBottom: 24,
      animation: 'fadeSlideUp 0.5s ease 0.15s both',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        position: 'relative',
      }}>
        {/* Connector line */}
        <div style={{
          position: 'absolute',
          top: 20,
          left: '10%', right: '10%',
          height: 1,
          background: 'linear-gradient(90deg, rgba(59,130,246,0.4) 0%, rgba(139,92,246,0.4) 50%, rgba(6,182,212,0.4) 100%)',
          zIndex: 0,
        }} />

        {STEPS.map((step, i) => {
          const delay = i * 100
          const Icon = step.icon
          return (
            <div
              key={step.key}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                gap: 10, zIndex: 1, flex: 1,
                animation: `fadeSlideUp 0.4s ease ${delay}ms both`,
              }}
            >
              {/* Circle */}
              <div style={{
                width: 40, height: 40, borderRadius: '50%',
                background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(139,92,246,0.2))',
                border: '2px solid rgba(59,130,246,0.5)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                position: 'relative',
                boxShadow: '0 0 14px rgba(59,130,246,0.2)',
              }}>
                <Icon size={16} color="#93C5FD" />
                {/* Check mark overlay */}
                <div style={{
                  position: 'absolute', bottom: -4, right: -4,
                  width: 16, height: 16, borderRadius: '50%',
                  background: '#10B981',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '2px solid var(--bg-surface)',
                }}>
                  <Check size={9} color="#fff" strokeWidth={3} />
                </div>
              </div>
              <span style={{
                fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
                textAlign: 'center', whiteSpace: 'nowrap',
                letterSpacing: '-0.01em',
              }}>
                {step.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
