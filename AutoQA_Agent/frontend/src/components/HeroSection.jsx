import { useState } from 'react'
import { Search, Zap } from 'lucide-react'

const STATUS_STEPS = [
  'Connecting to GitHub…',
  'Cloning repository…',
  'Detecting tech stack…',
  'Discovering API routes…',
  'Running local Ollama analysis…',
  'Sending facts to Groq…',
  'Assembling report…',
]

export default function HeroSection({ onAnalyze, loading, error }) {
  const [url, setUrl] = useState('')
  const [stepIdx, setStepIdx] = useState(0)

  function handleSubmit(e) {
    e.preventDefault()
    if (!url.trim()) return
    setStepIdx(0)
    // Cycle through status messages while loading
    const interval = setInterval(() => {
      setStepIdx(i => {
        if (i >= STATUS_STEPS.length - 1) { clearInterval(interval); return i }
        return i + 1
      })
    }, 2800)
    onAnalyze(url).finally(() => clearInterval(interval))
  }

  return (
    <div style={{
      position: 'relative',
      borderRadius: 24,
      overflow: 'hidden',
      padding: '56px 48px 48px',
      background: 'linear-gradient(135deg, rgba(15,22,41,0.95) 0%, rgba(20,27,46,0.95) 100%)',
      border: '1px solid var(--border)',
      marginBottom: 28,
      animation: 'fadeSlideUp 0.5s ease both',
    }}>

      {/* Ambient orbs */}
      <div style={{
        position: 'absolute', width: 500, height: 500,
        borderRadius: '50%', top: -200, left: -100,
        background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 65%)',
        pointerEvents: 'none',
        animation: 'orbFloat 8s ease-in-out infinite',
      }} />
      <div style={{
        position: 'absolute', width: 400, height: 400,
        borderRadius: '50%', bottom: -150, right: -80,
        background: 'radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 65%)',
        pointerEvents: 'none',
        animation: 'orbFloat 10s ease-in-out infinite reverse',
      }} />

      {/* Badge */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '4px 12px', borderRadius: 99,
        background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)',
        marginBottom: 24, position: 'relative',
      }}>
        <div style={{
          width: 6, height: 6, borderRadius: '50%',
          background: '#3B82F6',
          animation: 'pulseGlow 2s ease infinite',
        }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: '#93C5FD', letterSpacing: '0.06em' }}>
          AI-POWERED · CODE-FIRST ANALYSIS
        </span>
      </div>

      {/* Heading */}
      <h1 style={{
        fontSize: 'clamp(28px, 4vw, 48px)',
        fontWeight: 900,
        letterSpacing: '-0.03em',
        lineHeight: 1.08,
        marginBottom: 16,
        position: 'relative',
        maxWidth: 640,
      }}>
        <span style={{
          background: 'linear-gradient(135deg, #F8FAFC 0%, #94A3B8 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}>
          Repository Intelligence,{' '}
        </span>
        <span style={{
          background: 'linear-gradient(135deg, #93C5FD 0%, #A78BFA 60%, #67E8F9 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          backgroundSize: '200% 100%',
          animation: 'gradientShift 5s ease infinite',
        }}>
          Automated.
        </span>
      </h1>

      <p style={{
        fontSize: 16, color: 'var(--text-secondary)',
        lineHeight: 1.65, maxWidth: 520, marginBottom: 36,
        position: 'relative',
      }}>
        Analyze GitHub repositories — detect tech stacks, discover APIs, and generate
        AI insights using local Ollama and Groq.
      </p>

      {/* Input form */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 10, maxWidth: 680, position: 'relative' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <div style={{
            position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--text-muted)', pointerEvents: 'none',
            display: 'flex', alignItems: 'center',
          }}>
            <Search size={15} />
          </div>
          <input
            id="github-url-input"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://github.com/owner/repository"
            required
            disabled={loading}
            style={{
              width: '100%', paddingLeft: 42, paddingRight: 16,
              paddingTop: 14, paddingBottom: 14,
              background: 'rgba(11,16,32,0.7)',
              border: '1px solid var(--border)',
              borderRadius: 12, color: 'var(--text-primary)',
              fontSize: 14, outline: 'none',
              fontFamily: 'Inter, sans-serif',
              transition: 'border-color 0.2s, box-shadow 0.2s',
              backdropFilter: 'blur(8px)',
            }}
            onFocus={e => {
              e.target.style.borderColor = 'rgba(59,130,246,0.5)'
              e.target.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.08)'
            }}
            onBlur={e => {
              e.target.style.borderColor = 'var(--border)'
              e.target.style.boxShadow = 'none'
            }}
          />
        </div>
        <button
          id="analyze-btn"
          type="submit"
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: loading
              ? 'rgba(30,40,65,0.9)'
              : 'linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)',
            color: '#fff', border: 'none', borderRadius: 12,
            padding: '14px 28px', fontWeight: 700, fontSize: 14,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s', whiteSpace: 'nowrap',
            boxShadow: loading ? 'none' : '0 4px 20px rgba(59,130,246,0.35)',
            fontFamily: 'Inter, sans-serif',
            letterSpacing: '-0.01em',
            opacity: loading ? 0.8 : 1,
          }}
          onMouseEnter={e => {
            if (!loading) e.currentTarget.style.transform = 'translateY(-1px)'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.transform = ''
          }}
        >
          {loading
            ? <><SpinnerIcon /> Analyzing</>
            : <><Zap size={14} /> Analyze</>
          }
        </button>
      </form>

      {/* Status line */}
      {loading && (
        <div style={{
          marginTop: 14, display: 'flex', alignItems: 'center', gap: 8,
          animation: 'fadeIn 0.3s ease',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#3B82F6',
            animation: 'pulseGlow 1s ease infinite',
          }} />
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
            {STATUS_STEPS[stepIdx]}
          </span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div style={{
          marginTop: 14, padding: '10px 14px',
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: 10, color: '#FCA5A5', fontSize: 13,
          display: 'flex', alignItems: 'center', gap: 8,
          animation: 'fadeIn 0.3s ease',
        }}>
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}

function SpinnerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
      style={{ animation: 'spin 0.7s linear infinite', flexShrink: 0 }}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  )
}
