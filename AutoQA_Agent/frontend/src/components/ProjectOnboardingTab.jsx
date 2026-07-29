import { useState, useEffect } from 'react'
import { getProjectOnboarding } from '../api/client'
import { BookOpen, CheckCircle, HelpCircle, FileText, ArrowRight, ShieldCheck, Database, Server } from 'lucide-react'

export default function ProjectOnboardingTab({ analysisId, reportData }) {
  const [onboarding, setOnboarding] = useState(reportData?.project_onboarding || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedAnswers, setSelectedAnswers] = useState({})

  useEffect(() => {
    if (!onboarding && analysisId) {
      setLoading(true)
      getProjectOnboarding(analysisId)
        .then(data => setOnboarding(data))
        .catch(err => setError(err.message))
        .finally(() => setLoading(false))
    }
  }, [analysisId, onboarding])

  if (loading) return <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Building developer onboarding roadmap…</div>
  if (error) return <div style={{ padding: 24, color: '#f87171' }}>⚠️ {error}</div>
  if (!onboarding) return null

  const readingPath = onboarding.recommended_reading_path || []
  const quizzes = onboarding.quizzes || []

  function handleOptionSelect(quizIdx, optionIdx) {
    setSelectedAnswers(prev => ({ ...prev, [quizIdx]: optionIdx }))
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1100, margin: '0 auto', animation: 'fadeIn 0.3s ease both' }}>
      
      {/* Header Banner */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24,
        display: 'flex', alignItems: 'center', gap: 16
      }}>
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(20,210,160,0.15)', color: 'var(--accent-teal)' }}>
          <BookOpen size={28} />
        </div>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            Developer Onboarding Roadmap & Guide
          </h3>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
            Recommended reading order, core architectural components, and interactive codebase comprehension quizzes.
          </p>
        </div>
      </div>

      {/* Recommended Reading Path Walkthrough */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <h4 style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={18} style={{ color: 'var(--accent-teal)' }} /> Recommended Reading Order
        </h4>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {readingPath.map((item) => (
            <div key={item.step} style={{
              display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px',
              background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%', background: 'rgba(20,210,160,0.15)',
                color: 'var(--accent-teal)', fontWeight: 800, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {item.step}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{item.title}</span>
                  <span style={{ fontSize: 10, fontWeight: 800, padding: '2px 6px', borderRadius: 4, background: item.importance === 'CRITICAL' ? 'rgba(239,68,68,0.15)' : 'rgba(99,102,241,0.15)', color: item.importance === 'CRITICAL' ? '#f87171' : '#a5b4fc' }}>
                    {item.importance}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{item.reason}</div>
              </div>

              <div style={{ fontSize: 12, fontFamily: "'Fira Code', monospace", color: 'var(--accent-teal)', background: 'var(--bg-surface)', padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)' }}>
                {item.file_path}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Component Summaries Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: '#f87171', fontWeight: 700, fontSize: 13 }}>
            <ShieldCheck size={16} /> Authentication & Security Flow
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {onboarding.auth_flow_summary}
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: '#facc15', fontWeight: 700, fontSize: 13 }}>
            <Database size={16} /> Database & Data Models Layer
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {onboarding.database_layer_summary}
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--accent-teal)', fontWeight: 700, fontSize: 13 }}>
            <Server size={16} /> Core API & Endpoints Architecture
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {onboarding.core_apis_summary}
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: '#a5b4fc', fontWeight: 700, fontSize: 13 }}>
            <BookOpen size={16} /> Business Logic Modules
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {onboarding.business_logic_summary}
          </div>
        </div>

      </div>

      {/* Interactive Codebase Quizzes */}
      {quizzes.length > 0 && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <h4 style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <HelpCircle size={18} style={{ color: '#a5b4fc' }} /> Interactive Codebase Quizzes
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {quizzes.map((quiz, qIdx) => {
              const selected = selectedAnswers[qIdx]
              const hasAnswered = selected !== undefined

              return (
                <div key={qIdx} style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                    Q{qIdx + 1}: {quiz.question}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                    {quiz.options.map((opt, oIdx) => {
                      let bg = 'var(--bg-surface)'
                      let border = 'var(--border)'
                      let color = 'var(--text-primary)'

                      if (hasAnswered) {
                        if (opt.is_correct) {
                          bg = 'rgba(20,210,160,0.15)'
                          border = 'rgba(20,210,160,0.4)'
                          color = 'var(--accent-teal)'
                        } else if (selected === oIdx) {
                          bg = 'rgba(239,68,68,0.15)'
                          border = 'rgba(239,68,68,0.4)'
                          color = '#f87171'
                        }
                      }

                      return (
                        <button
                          key={oIdx}
                          onClick={() => handleOptionSelect(qIdx, oIdx)}
                          style={{
                            padding: '10px 14px', borderRadius: 8, background: bg, border: `1px solid ${border}`,
                            color: color, fontSize: 13, fontWeight: 600, textAlign: 'left', cursor: 'pointer', transition: 'all 0.15s'
                          }}
                        >
                          {opt.text}
                        </button>
                      )
                    })}
                  </div>

                  {hasAnswered && (
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'var(--bg-surface)', padding: '10px 14px', borderRadius: 6, border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>💡 {quiz.explanation}</span>
                      <span style={{ fontSize: 11, fontFamily: "'Fira Code', monospace", color: 'var(--accent-teal)' }}>
                        Citation: {quiz.citation_file}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

    </div>
  )
}
