import { useState } from 'react'
import { ChevronDown, BookOpen, Package, FileCode, FolderSearch } from 'lucide-react'

function AccordionItem({ icon: Icon, title, accent, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: 12, overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', background: open ? `${accent}07` : 'transparent',
          border: 'none', cursor: 'pointer', fontFamily: 'Inter, sans-serif',
          transition: 'background 0.2s',
          gap: 12,
        }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = 'rgba(255,255,255,0.025)' }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'transparent' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: `${accent}14`, border: `1px solid ${accent}22`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <Icon size={13} color={accent} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
        </div>
        <ChevronDown
          size={15}
          color="var(--text-muted)"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.25s ease', flexShrink: 0 }}
        />
      </button>

      <div style={{
        maxHeight: open ? '600px' : '0px',
        overflow: 'hidden',
        transition: 'max-height 0.35s ease',
      }}>
        <div style={{ padding: '14px 18px 18px', borderTop: `1px solid ${accent}12` }}>
          {children}
        </div>
      </div>
    </div>
  )
}

export default function EvidenceAccordion({ report }) {
  if (!report) return null

  const { readme_summary, module_summaries = {}, project_structure_summary } = report
  const importantFiles = project_structure_summary?.important_files || []
  const modules = Object.entries(module_summaries)

  const hasContent = readme_summary || importantFiles.length > 0 || modules.length > 0
  if (!hasContent) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.3s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
        background: 'linear-gradient(90deg, rgba(16,185,129,0.04) 0%, transparent 60%)',
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 9,
          background: 'rgba(16,185,129,0.1)',
          border: '1px solid rgba(16,185,129,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <FolderSearch size={16} color="#6EE7B7" />
        </div>
        <div>
          <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>Repository Evidence</h3>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
            Verified facts · Ollama local analysis
          </p>
        </div>
      </div>

      {/* Accordion items */}
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>

        {readme_summary && (
          <AccordionItem icon={BookOpen} title="README Summary" accent="#10B981">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.75 }}>
              {readme_summary}
            </p>
          </AccordionItem>
        )}

        {modules.length > 0 && (
          <AccordionItem icon={Package} title={`Detected Modules (${modules.length})`} accent="#A78BFA">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {modules.map(([name, summary]) => (
                <div key={name} style={{
                  padding: '10px 12px', borderRadius: 8,
                  background: 'rgba(167,139,250,0.04)',
                  border: '1px solid rgba(167,139,250,0.12)',
                }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#C4B5FD', marginBottom: 4, fontFamily: 'JetBrains Mono, monospace' }}>
                    {name}/
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{summary}</div>
                </div>
              ))}
            </div>
          </AccordionItem>
        )}

        {importantFiles.length > 0 && (
          <AccordionItem icon={FileCode} title={`Important Files (${importantFiles.length})`} accent="#06B6D4">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {importantFiles.map(file => (
                <span key={file} style={{
                  fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 6,
                  background: 'rgba(6,182,212,0.07)',
                  border: '1px solid rgba(6,182,212,0.18)',
                  color: '#67E8F9',
                  fontFamily: 'JetBrains Mono, monospace',
                }}>
                  {file}
                </span>
              ))}
            </div>
          </AccordionItem>
        )}
      </div>
    </div>
  )
}
