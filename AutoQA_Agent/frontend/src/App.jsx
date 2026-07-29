import { useState, useEffect, useRef } from 'react'
import { analyzeRepository, getAnalysis, getAnalysisStatus, downloadPdf, emailReport } from './api/client'
import { MessageSquare, Network, Bug, GitBranch, Download, Loader2, CornerDownRight, Mail, X, CheckCircle, Database, ShieldAlert, BookOpen, Activity, Wrench, GitCompare, Layers, GitGraph, Map } from 'lucide-react'

import QAChatPanel from './components/QAChatPanel'
import DependencyGraphPanel from './components/DependencyGraphPanel'
import BugReportPanel from './components/BugReportPanel'
import ArchitectureTab from './components/ArchitectureTab'
import AgentPipelineView from './components/AgentPipelineView'

import ImpactAnalysisTab from './components/ImpactAnalysisTab'
import ArchitectureDriftTab from './components/ArchitectureDriftTab'
import ProjectOnboardingTab from './components/ProjectOnboardingTab'
import RepositoryHealthTab from './components/RepositoryHealthTab'
import TechnicalDebtTab from './components/TechnicalDebtTab'
import CrossRepoCompareModal from './components/CrossRepoCompareModal'
import ExecutionFlowTab from './components/ExecutionFlowTab'
import FeatureMapTab from './components/FeatureMapTab'

import './index.css'

const STATUS_STEPS = [
  'Connecting to GitHub…',
  'Cloning repository…',
  'Detecting tech stack…',
  'Discovering API routes…',
  'Running local Ollama analysis…',
  'Sending facts to Groq…',
  'Assembling report…',
]

const TABS = [
  { id: 'chat',         label: 'Q&A Chat',        icon: MessageSquare },
  { id: 'graph',        label: 'Dependency Graph', icon: Network },
  { id: 'bugs',         label: 'Bug Report',       icon: Bug },
  { id: 'architecture', label: 'Architecture',     icon: GitBranch },
  { id: 'impact',       label: 'Impact Analysis',  icon: Layers },
  { id: 'drift',        label: 'Arch Drift',       icon: ShieldAlert },
  { id: 'onboarding',   label: 'Onboarding',       icon: BookOpen },
  { id: 'health',       label: 'Health Score',     icon: Activity },
  { id: 'debt',         label: 'Tech Debt',        icon: Wrench },
  { id: 'execflow',     label: 'Execution Flow',   icon: GitGraph },
  { id: 'featuremap',   label: 'Feature Map',      icon: Map },
]

const POLL_INTERVAL_MS = 1000

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
      style={{ animation: 'spin 0.7s linear infinite', flexShrink: 0 }}>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  )
}

export default function App() {
  const [activeTab, setActiveTab]       = useState('chat')
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState('')
  const [report, setReport]             = useState(null)
  const [pdfLoading, setPdfLoading]     = useState(false)
  const [url, setUrl]                   = useState('')
  // Chat messages lifted here so conversation persists across tab switches.
  // Reset to [] whenever a new analysis starts.
  const [chatMessages, setChatMessages] = useState([])
  // Email modal state
  const [emailModalOpen, setEmailModalOpen] = useState(false)
  const [emailInput, setEmailInput]         = useState('')
  const [emailLoading, setEmailLoading]     = useState(false)
  const [emailToast, setEmailToast]         = useState(null) // { type: 'success'|'error', msg: string }

  // Cross-Repo modal state
  const [crossRepoModalOpen, setCrossRepoModalOpen] = useState(false)

  // Pipeline visualization state
  const [pipelineActive, setPipelineActive] = useState(false)  // show AgentPipelineView?
  const [pipelineAgents, setPipelineAgents] = useState([])      // live agent list
  const [currentAnalysisId, setCurrentAnalysisId] = useState(null)
  const [cachedFlash, setCachedFlash]       = useState(false)   // brief cache-hit indicator
  const pollRef = useRef(null)  // stores the setInterval id

  // ── Polling loop ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!pipelineActive || !currentAnalysisId) return

    pollRef.current = setInterval(async () => {
      try {
        const status = await getAnalysisStatus(currentAnalysisId)
        if (!status) return
        setPipelineAgents(status.agents || [])

        if (status.complete) {
          clearInterval(pollRef.current)
          // Fetch the full report now that pipeline is done
          try {
            const reportData = await getAnalysis(currentAnalysisId)
            setReport(reportData)
          } catch {
            setError('Analysis completed but report could not be fetched.')
          } finally {
            setLoading(false)
            // Wait one frame then fade pipeline out
            setTimeout(() => setPipelineActive(false), 600)
          }
        }
      } catch {
        // polling errors are transient; don't blow up the UI
      }
    }, POLL_INTERVAL_MS)

    return () => clearInterval(pollRef.current)
  }, [pipelineActive, currentAnalysisId])

  async function handleAnalyze(e) {
    e && e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return
    setError('')
    setReport(null)
    setPipelineActive(false)
    setPipelineAgents([])
    setCachedFlash(false)
    setChatMessages([])   // new repo → fresh conversation
    setLoading(true)

    try {
      const data = await analyzeRepository(trimmed)

      // ── Cache-hit path: backend returned the full report synchronously ──
      if (data.cached && data.report) {
        setReport(data.report)
        setLoading(false)
        setCachedFlash(true)
        setTimeout(() => setCachedFlash(false), 4000)
        return
      }

      // ── Async path: backend queued background analysis ──
      setCurrentAnalysisId(data.analysis_id)
      setPipelineActive(true)
      // Polling will start via the useEffect above and update state
      // setLoading stays true until polling detects complete
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  async function handleDownloadPdf() {
    if (!report) return
    setPdfLoading(true)
    try {
      await downloadPdf(report.analysis_id, report.repository_name)
    } catch (err) {
      setError('PDF download failed: ' + err.message)
    } finally {
      setPdfLoading(false)
    }
  }

  /* ── Email report ── */
  const _emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  function showToast(type, msg) {
    setEmailToast({ type, msg })
    setTimeout(() => setEmailToast(null), 5000)
  }

  async function handleSendEmail(e) {
    e.preventDefault()
    const addr = emailInput.trim()
    if (!_emailRegex.test(addr)) {
      showToast('error', 'Please enter a valid email address.')
      return
    }
    setEmailLoading(true)
    try {
      await emailReport(report.analysis_id, addr)
      setEmailModalOpen(false)
      setEmailInput('')
      showToast('success', `Report sent to ${addr} ✔`)
    } catch (err) {
      showToast('error', err.message)
    } finally {
      setEmailLoading(false)
    }
  }

  /* ── short repo name for display ── */
  const repoName = report?.repository_name
    ? report.repository_name.replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '')
    : ''

  // `number_of_files` is the correct field from RepositoryAnalysisReport schema.
  // `code_insights.analyzed_files` is the list of files actually deep-analyzed.
  const files  = report?.number_of_files ?? 0
  const chunks = report?.code_insights?.analyzed_files?.length ?? 0
  const hasGraph = !!(report?.dependency_graph?.nodes?.length)

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-app)' }}>

      {/* ── NAVBAR ── */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(8,13,24,0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 32px', height: 52,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent-teal) 0%, #0891b2 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
          </div>
          <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            AutoQA<span style={{ color: 'var(--accent-teal)' }}>.Agent</span>
          </span>
        </div>

        {/* Right nav */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          {report && (
            <>
              {/* Download PDF */}
              <button
                id="download-report-btn"
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '6px 14px', borderRadius: 8,
                  background: pdfLoading ? 'rgba(20,210,160,0.08)' : 'rgba(20,210,160,0.1)',
                  border: '1px solid rgba(20,210,160,0.3)',
                  color: 'var(--accent-teal)',
                  fontSize: 12, fontWeight: 600, cursor: pdfLoading ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s', opacity: pdfLoading ? 0.7 : 1,
                }}
                onMouseEnter={e => { if (!pdfLoading) { e.currentTarget.style.background = 'rgba(20,210,160,0.18)' } }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(20,210,160,0.1)' }}
              >
                {pdfLoading ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Download size={12} />}
                Download Report
              </button>

              {/* Email PDF */}
              <button
                id="email-report-btn"
                onClick={() => setEmailModalOpen(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '6px 14px', borderRadius: 8,
                  background: 'rgba(99,102,241,0.1)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  color: '#a5b4fc',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.1)' }}
              >
                <Mail size={12} />
                Email Report
              </button>

              {/* Cross-Repo Compare */}
              <button
                id="cross-repo-btn"
                onClick={() => setCrossRepoModalOpen(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '6px 14px', borderRadius: 8,
                  background: 'rgba(234,179,8,0.1)',
                  border: '1px solid rgba(234,179,8,0.3)',
                  color: '#facc15',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(234,179,8,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(234,179,8,0.1)' }}
              >
                <GitCompare size={12} />
                Cross-Repo Compare
              </button>
            </>
          )}
        </div>
      </nav>

      {/* ── HERO ── */}
      <section
        className="hero-grid"
        style={{
          position: 'relative', overflow: 'hidden',
          padding: '80px 32px 88px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
          borderBottom: '1px solid var(--border)',
          background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(20,210,160,0.07) 0%, transparent 65%)',
        }}
      >
        {/* Pill badge */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '5px 14px', borderRadius: 99,
          border: '1px solid rgba(20,210,160,0.3)',
          background: 'rgba(20,210,160,0.06)',
          marginBottom: 28,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-teal)', animation: 'pulseGlow 1.5s ease infinite', display: 'inline-block' }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-teal)', letterSpacing: '0.1em' }}>
            AI-POWERED STATIC ANALYSIS · LLM-BACKED
          </span>
        </div>

        {/* Headline */}
        <h1 style={{
          fontSize: 'clamp(36px, 6vw, 64px)',
          fontWeight: 900,
          letterSpacing: '-0.04em',
          lineHeight: 1.05,
          marginBottom: 20,
          maxWidth: 760,
        }}>
          <span style={{ color: 'var(--text-primary)' }}>Understand any codebase</span>
          <br />
          <span className="gradient-text-hero">in seconds, not weeks.</span>
        </h1>

        {/* Sub-headline */}
        <p style={{
          fontSize: 16, color: 'var(--text-secondary)', lineHeight: 1.7,
          maxWidth: 520, marginBottom: 40,
        }}>
          Paste a GitHub repo. We'll embed the code, map dependencies, surface bugs,
          and let you ask anything in plain English —{' '}
          <strong style={{ color: 'var(--text-primary)' }}>with citations.</strong>
        </p>

        {/* Input row */}
        <form
          id="analyze-form"
          onSubmit={handleAnalyze}
          style={{ display: 'flex', gap: 10, width: '100%', maxWidth: 620, position: 'relative' }}
        >
          <div style={{ flex: 1, position: 'relative' }}>
            <div style={{
              position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
              color: 'var(--text-muted)', pointerEvents: 'none',
            }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22" />
              </svg>
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
                paddingTop: 15, paddingBottom: 15,
                background: 'rgba(14,21,37,0.9)',
                border: '1px solid rgba(20,210,160,0.25)',
                borderRadius: 10, color: 'var(--text-primary)',
                fontSize: 14, outline: 'none',
                fontFamily: 'Inter, sans-serif',
                transition: 'border-color 0.2s, box-shadow 0.2s',
                backdropFilter: 'blur(8px)',
              }}
              onFocus={e => {
                e.target.style.borderColor = 'rgba(20,210,160,0.5)'
                e.target.style.boxShadow = '0 0 0 3px rgba(20,210,160,0.08)'
              }}
              onBlur={e => {
                e.target.style.borderColor = 'rgba(20,210,160,0.25)'
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
              background: loading ? 'rgba(20,210,160,0.15)' : 'var(--accent-teal)',
              color: loading ? 'var(--accent-teal)' : '#0a1628',
              border: 'none', borderRadius: 10,
              padding: '15px 26px', fontWeight: 700, fontSize: 14,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s', whiteSpace: 'nowrap',
              fontFamily: 'Inter, sans-serif',
              letterSpacing: '-0.01em',
              boxShadow: loading ? 'none' : '0 4px 20px rgba(20,210,160,0.35)',
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave={e => { e.currentTarget.style.transform = '' }}
          >
            {loading ? <><Spinner /> Analysing</> : <><CornerDownRight size={14} /> Analyse</>}
          </button>
        </form>

        {/* Status / hint — only show when loading but pipeline not yet active */}
        {loading && !pipelineActive && (
          <p style={{ marginTop: 14, fontSize: 12, color: 'var(--text-muted)', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-teal)', animation: 'pulseGlow 1s ease infinite', display: 'inline-block' }} />
            Connecting…
          </p>
        )}
        {!loading && !report && (
          <p style={{ marginTop: 14, fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            PRESS <kbd style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 4, padding: '1px 5px', fontSize: 10 }}>Enter</kbd> TO INDEX
          </p>
        )}

        {/* Cache-hit flash */}
        {cachedFlash && (
          <div style={{
            marginTop: 14, padding: '8px 16px',
            background: 'rgba(20,210,160,0.08)', border: '1px solid rgba(20,210,160,0.25)',
            borderRadius: 8, color: 'var(--accent-teal)', fontSize: 12,
            display: 'flex', alignItems: 'center', gap: 8,
            animation: 'fadeIn 0.3s ease both',
          }}>
            <Database size={12} /> Loaded from cache — no re-analysis needed
          </div>
        )}

        {error && !loading && (
          <div style={{
            marginTop: 14, padding: '10px 16px',
            background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: 8, color: '#F87171', fontSize: 13,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* Outputs strip */}
        {!report && (
          <div style={{ marginTop: 48, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.12em', fontWeight: 600, textTransform: 'uppercase' }}>OUTPUTS</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              {['Q&A CHAT', 'DEPENDENCY GRAPH', 'BUG REPORTS', 'ARCH DIAGRAM'].map((label, i) => (
                <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{label}</span>
                  {i < 3 && <span style={{ color: 'var(--border)', fontSize: 14 }}>·</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ── PIPELINE VIEW (during active analysis) ── */}
      {pipelineActive && (
        <div style={
          {
            flex: 1,
            display: 'flex',
            justifyContent: 'center',
            borderTop: '1px solid var(--border)',
            background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(99,102,241,0.04) 0%, transparent 65%)',
            animation: report ? 'fadeIn 0.5s ease reverse both' : 'fadeIn 0.4s ease both',
          }
        }>
          <AgentPipelineView agents={pipelineAgents} repoUrl={url.trim()} />
        </div>
      )}

      {/* ── RESULTS AREA ── */}
      {(report && !pipelineActive) && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', animation: 'fadeIn 0.4s ease both' }}>

          {/* Status bar (repo info + stats) */}
          {report && (
            <div style={{
              background: 'var(--bg-surface)',
              borderBottom: '1px solid var(--border)',
              padding: '10px 32px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              gap: 16,
              animation: 'fadeIn 0.4s ease both',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 30, height: 30, borderRadius: '50%',
                  background: 'rgba(20,210,160,0.15)',
                  border: '1.5px solid rgba(20,210,160,0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-teal)', display: 'inline-block' }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                    {repoName || report.repository_name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
                    Repository indexed ({chunks} chunks found)
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
                {[
                  { label: 'FILES',  value: files },
                  { label: 'CHUNKS', value: chunks },
                  { label: 'GRAPH',  value: hasGraph ? 'Ready' : 'N/A' },
                ].map(stat => (
                  <div key={stat.label} style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em', fontWeight: 600 }}>{stat.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: stat.label === 'GRAPH' && hasGraph ? 'var(--accent-teal)' : 'var(--text-primary)', marginTop: 2 }}>{stat.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}


          {/* Loading skeleton */}
          {loading && !report && (
            <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="skeleton" style={{ height: 54 }} />
              <div className="skeleton" style={{ height: 36 }} />
              <div className="skeleton" style={{ height: 420 }} />
            </div>
          )}

          {/* Sub-nav tabs */}
          {report && (
            <>
              <div style={{
                background: 'var(--bg-surface)',
                borderBottom: '1px solid var(--border)',
                padding: '0 32px',
                display: 'flex', alignItems: 'center', gap: 4,
              }}>
                {TABS.map(t => {
                  const Icon = t.icon
                  const isActive = activeTab === t.id
                  return (
                    <button
                      key={t.id}
                      id={`tab-${t.id}`}
                      onClick={() => setActiveTab(t.id)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 7,
                        padding: '14px 20px',
                        background: 'transparent',
                        color: isActive ? 'var(--accent-teal)' : 'var(--text-secondary)',
                        border: 'none',
                        borderBottom: `2px solid ${isActive ? 'var(--accent-teal)' : 'transparent'}`,
                        fontSize: 13, fontWeight: isActive ? 600 : 500,
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                        whiteSpace: 'nowrap',
                        letterSpacing: '-0.01em',
                      }}
                      onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-primary)' }}
                      onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--text-secondary)' }}
                    >
                      <Icon size={14} />
                      {t.label}
                    </button>
                  )
                })}
              </div>

              {/* Tab panels */}
              <div style={{ flex: 1, padding: '24px 32px 40px', maxWidth: 1100, width: '100%', margin: '0 auto', alignSelf: 'stretch' }}>
                {activeTab === 'chat' && <QAChatPanel report={report} messages={chatMessages} setMessages={setChatMessages} />}
                {activeTab === 'graph' && (
                  <DependencyGraphPanel
                    dependencyGraph={report.dependency_graph || report.code_insights?.dependency_graph}
                  />
                )}
                {activeTab === 'bugs' && <BugReportPanel codeInsights={report.code_insights} />}
                {activeTab === 'architecture' && <ArchitectureTab report={report} />}
                {activeTab === 'impact' && (
                  <ImpactAnalysisTab
                    analysisId={report.analysis_id}
                    fileList={report.code_insights?.analyzed_files || []}
                  />
                )}
                {activeTab === 'drift' && (
                  <ArchitectureDriftTab
                    analysisId={report.analysis_id}
                    reportData={report}
                  />
                )}
                {activeTab === 'onboarding' && (
                  <ProjectOnboardingTab
                    analysisId={report.analysis_id}
                    reportData={report}
                  />
                )}
                {activeTab === 'health' && (
                  <RepositoryHealthTab
                    analysisId={report.analysis_id}
                    reportData={report}
                  />
                )}
                {activeTab === 'debt' && (
                  <TechnicalDebtTab
                    analysisId={report.analysis_id}
                    reportData={report}
                  />
                )}
                {activeTab === 'execflow' && (
                  <ExecutionFlowTab
                    analysisId={report.analysis_id}
                    report={report}
                  />
                )}
                {activeTab === 'featuremap' && (
                  <FeatureMapTab
                    analysisId={report.analysis_id}
                    report={report}
                  />
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── FOOTER ── */}
      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: '18px 32px',
        textAlign: 'center',
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: '0.12em',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        background: 'var(--bg-app)',
      }}>
        BUILT FOR DEVELOPERS · POWERED BY EMBEDDINGS + LLM REASONING
      </footer>

      {/* ── Cross-Repo Compare Modal ── */}
      <CrossRepoCompareModal
        isOpen={crossRepoModalOpen}
        onClose={() => setCrossRepoModalOpen(false)}
        currentAnalysisId={report?.analysis_id}
      />

      {/* ── Email modal ── */}
      {emailModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Email report"
          onClick={e => { if (e.target === e.currentTarget) setEmailModalOpen(false) }}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <div style={{
            background: 'var(--bg-card, #1a1a2e)',
            border: '1px solid rgba(99,102,241,0.35)',
            borderRadius: 16,
            padding: '32px 28px 28px',
            width: '100%', maxWidth: 420,
            boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
            animation: 'fadeInUp 0.18s ease',
          }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 8,
                  background: 'rgba(99,102,241,0.15)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Mail size={16} color="#a5b4fc" />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>Email Report</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Send the PDF to your inbox</div>
                </div>
              </div>
              <button
                onClick={() => { setEmailModalOpen(false); setEmailInput('') }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Repo context */}
            <div style={{
              background: 'rgba(99,102,241,0.06)',
              border: '1px solid rgba(99,102,241,0.15)',
              borderRadius: 8, padding: '8px 12px', marginBottom: 18,
              fontSize: 11, color: 'var(--text-muted)',
            }}>
              📦 <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{report?.repository_name}</span>
            </div>

            {/* Form */}
            <form onSubmit={handleSendEmail}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                Recipient email
              </label>
              <input
                id="email-recipient-input"
                type="email"
                placeholder="you@example.com"
                value={emailInput}
                onChange={e => setEmailInput(e.target.value)}
                autoFocus
                disabled={emailLoading}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  padding: '10px 14px', borderRadius: 8,
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(99,102,241,0.3)',
                  color: 'var(--text-primary)',
                  fontSize: 13, outline: 'none',
                  marginBottom: 18,
                  transition: 'border-color 0.15s',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.7)' }}
                onBlur={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)' }}
              />
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => { setEmailModalOpen(false); setEmailInput('') }}
                  style={{
                    flex: 1, padding: '9px 0', borderRadius: 8, cursor: 'pointer',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: 'var(--text-muted)', fontSize: 12, fontWeight: 600,
                  }}
                >
                  Cancel
                </button>
                <button
                  id="email-send-btn"
                  type="submit"
                  disabled={emailLoading || !emailInput.trim()}
                  style={{
                    flex: 2, padding: '9px 0', borderRadius: 8,
                    background: emailLoading ? 'rgba(99,102,241,0.4)' : 'rgba(99,102,241,0.85)',
                    border: '1px solid rgba(99,102,241,0.5)',
                    color: '#fff', fontSize: 12, fontWeight: 700,
                    cursor: emailLoading || !emailInput.trim() ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                    transition: 'background 0.15s',
                    opacity: !emailInput.trim() ? 0.6 : 1,
                  }}
                >
                  {emailLoading
                    ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Sending…</>
                    : <><Mail size={12} /> Send Report</>
                  }
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Toast notification ── */}
      {emailToast && (
        <div
          role="alert"
          style={{
            position: 'fixed', bottom: 28, right: 28, zIndex: 10000,
            display: 'flex', alignItems: 'flex-start', gap: 10,
            background: emailToast.type === 'success' ? 'rgba(20,210,160,0.12)' : 'rgba(239,68,68,0.12)',
            border: `1px solid ${emailToast.type === 'success' ? 'rgba(20,210,160,0.4)' : 'rgba(239,68,68,0.4)'}`,
            borderRadius: 10,
            padding: '12px 16px',
            maxWidth: 360,
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            animation: 'fadeInUp 0.2s ease',
          }}
        >
          <span style={{ fontSize: 16 }}>{emailToast.type === 'success' ? '✅' : '❌'}</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
              {emailToast.type === 'success' ? 'Email sent!' : 'Email failed'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{emailToast.msg}</div>
          </div>
          <button
            onClick={() => setEmailToast(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', marginLeft: 4, padding: 0 }}
          >
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  )
}
