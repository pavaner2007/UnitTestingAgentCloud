import { useState, useRef, useEffect } from 'react'
import { Send, FileText, AlertCircle, Loader2 } from 'lucide-react'
import { askCodebaseQuestion } from '../api/client'

const EXAMPLE_PROMPTS = [
  'Where is authentication handled?',
  'How does the routing work?',
  'What database models are defined?',
  'Where are external API calls executed?',
]

export default function QAChatPanel({ report, messages, setMessages }) {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef(null)

  const analysisId = report?.analysis_id

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend(questionText) {
    const q = (questionText || input).trim()
    if (!q || loading || !analysisId) return

    setInput('')
    setError('')
    const userMsg = { sender: 'user', text: q, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await askCodebaseQuestion(analysisId, q)
      setMessages(prev => [...prev, {
        sender: 'ai',
        text: res.answer,
        citations: res.citations || [],
        timestamp: new Date(),
      }])
    } catch (err) {
      setError(err.message || 'Failed to get an answer.')
    } finally {
      setLoading(false)
    }
  }

  if (!report) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      height: 580,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.45s ease both',
    }}>
      {/* Messages scroll area */}
      <div style={{ flex: 1, padding: '28px 28px 16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Empty state */}
        {messages.length === 0 && (
          <div style={{
            margin: 'auto',
            textAlign: 'center',
            maxWidth: 480,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18,
          }}>
            {/* Icon circle */}
            <div style={{
              width: 58, height: 58, borderRadius: '50%',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {/* Sparkle-like icon matching reference */}
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--accent-teal)" strokeWidth="1.6">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                <circle cx="12" cy="12" r="2" fill="var(--accent-teal)" stroke="none" />
              </svg>
            </div>

            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                Ask anything about the codebase
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Try: "Where is authentication handled?" or "How does the routing work?"
              </p>
            </div>
          </div>
        )}

        {/* Message thread */}
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column',
            alignItems: m.sender === 'user' ? 'flex-end' : 'flex-start',
            gap: 6,
          }}>
            <div style={{
              maxWidth: '80%',
              padding: '13px 17px',
              borderRadius: 14,
              borderTopRightRadius: m.sender === 'user' ? 4 : 14,
              borderTopLeftRadius: m.sender === 'ai' ? 4 : 14,
              background: m.sender === 'user'
                ? 'linear-gradient(135deg, rgba(20,210,160,0.25), rgba(6,182,212,0.2))'
                : 'var(--bg-elevated)',
              border: m.sender === 'user'
                ? '1px solid rgba(20,210,160,0.3)'
                : '1px solid var(--border)',
              color: m.sender === 'user' ? '#e0f8f2' : 'var(--text-primary)',
              fontSize: 13,
              lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
            }}>
              {m.text}
            </div>

            {/* Citations */}
            {m.citations?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4, maxWidth: '80%' }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <FileText size={10} /> Context Citations:
                </span>
                {m.citations.map((c, idx) => (
                  <span key={idx} className="mono-code" style={{ fontSize: 10 }}>
                    {c.file}:{c.start_line}-{c.end_line}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', fontSize: 12 }}>
            <Loader2 size={15} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />
            Analyzing code context &amp; reasoning with Groq…
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            padding: '10px 14px', borderRadius: 10,
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)',
            color: '#F87171', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <AlertCircle size={13} />
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div style={{
        borderTop: '1px solid var(--border)',
        background: 'rgba(8,13,24,0.7)',
        padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <input
          id="qa-chat-input"
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSend() }}
          placeholder="Ask a question about the code..."
          disabled={loading}
          style={{
            flex: 1,
            background: 'rgba(14,21,37,0.8)',
            border: '1px solid var(--border)',
            borderRadius: 10,
            padding: '12px 16px',
            color: 'var(--text-primary)',
            fontSize: 13,
            outline: 'none',
            fontFamily: 'Inter, sans-serif',
            transition: 'border-color 0.2s',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(20,210,160,0.4)'}
          onBlur={e => e.target.style.borderColor = 'var(--border)'}
        />

        <button
          id="qa-send-btn"
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '12px 20px', borderRadius: 10,
            background: (loading || !input.trim()) ? 'rgba(20,210,160,0.12)' : 'var(--accent-teal)',
            color: (loading || !input.trim()) ? 'var(--accent-teal)' : '#07131f',
            border: (loading || !input.trim()) ? '1px solid rgba(20,210,160,0.2)' : 'none',
            fontSize: 13, fontWeight: 700,
            cursor: (loading || !input.trim()) ? 'not-allowed' : 'pointer',
            opacity: (loading || !input.trim()) ? 0.7 : 1,
            transition: 'all 0.15s',
            whiteSpace: 'nowrap',
          }}
        >
          <Send size={13} />
          Ask
        </button>
      </div>
    </div>
  )
}
