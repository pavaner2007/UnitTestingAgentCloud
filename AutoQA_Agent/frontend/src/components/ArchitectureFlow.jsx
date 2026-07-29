import { useState } from 'react'
import { Network, Layers, Sparkles, Server, Database, Globe, Cpu, ChevronRight, X } from 'lucide-react'

// Derive architecture nodes and edges from report
function buildGraphData(report) {
  if (!report) return { nodes: [], edges: [] }
  const stack = report.technology_stack || {}
  const moduleSummaries = report.code_insights?.module_summaries || report.module_summaries || {}
  const apis = report.api_inventory || []

  const seen = new Set()
  function unique(arr = []) {
    return arr.filter(v => {
      const key = v.toLowerCase().trim()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  const feItems = unique(stack.frontend || [])
  const beItems = unique(stack.backend || [])
  const fwItems = unique(stack.frameworks || [])
  const dbItems = unique(stack.databases || [])

  const nodes = []

  // 1. Frontend Node
  if (feItems.length) {
    nodes.push({
      id: 'frontend',
      label: 'Client / Presentation',
      type: 'Frontend',
      techs: feItems,
      icon: Globe,
      color: '#6366F1',
      details: 'Renders the UI and initiates client HTTP requests.',
      modules: Object.keys(moduleSummaries).filter(m => /ui|front|web|app|component|client/i.test(m)),
    })
  }

  // 2. API Gateway / Route Node
  if (report.number_of_apis_discovered > 0 || apis.length > 0) {
    nodes.push({
      id: 'api',
      label: 'API Gateway & Routes',
      type: 'Interface',
      techs: [`${report.number_of_apis_discovered || apis.length} Endpoints Discovered`],
      icon: Server,
      color: '#3B82F6',
      details: 'Exposes HTTP routes and dispatches incoming API payloads.',
      endpoints: apis.slice(0, 8),
    })
  }

  // 3. Business Logic Node
  const beLogic = [...beItems, ...fwItems]
  if (beLogic.length) {
    nodes.push({
      id: 'logic',
      label: 'Core Business Logic',
      type: 'Service Layer',
      techs: beLogic,
      icon: Cpu,
      color: '#06B6D4',
      details: 'Implements core services, domain algorithms, and data handlers.',
      modules: Object.keys(moduleSummaries).filter(m => !/ui|front|web|app|component|client|db|model|database/i.test(m)),
    })
  }

  // 4. Data Storage Node
  if (dbItems.length) {
    nodes.push({
      id: 'database',
      label: 'Data Persistence',
      type: 'Database',
      techs: dbItems,
      icon: Database,
      color: '#F59E0B',
      details: 'Stores structured domain entities and query indexes.',
      modules: Object.keys(moduleSummaries).filter(m => /db|model|database|repo|store/i.test(m)),
    })
  }

  // Build sequential directed edges
  const edges = []
  for (let i = 0; i < nodes.length - 1; i++) {
    edges.push({
      from: nodes[i].id,
      to: nodes[i + 1].id,
      color: nodes[i].color,
    })
  }

  return { nodes, edges }
}

export default function ArchitectureFlow({ report }) {
  const { nodes, edges } = buildGraphData(report)
  const [selectedNode, setSelectedNode] = useState(null)

  if (nodes.length < 2) return null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 18,
      overflow: 'hidden',
      animation: 'fadeSlideUp 0.5s ease 0.4s both',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justify: 'space-between',
        background: 'linear-gradient(90deg, rgba(59,130,246,0.04) 0%, transparent 60%)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'rgba(59,130,246,0.1)',
            border: '1px solid rgba(59,130,246,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Network size={16} color="#93C5FD" />
          </div>
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 15, lineHeight: 1 }}>System Architecture Flow</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
              Interactive node graph generated from code inspection
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
          <Sparkles size={13} color="#93C5FD" />
          <span>Click any node for details</span>
        </div>
      </div>

      {/* Graph Area */}
      <div style={{ padding: '28px 24px', position: 'relative' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${nodes.length}, 1fr)`,
          gap: 16,
          position: 'relative',
          alignItems: 'center',
        }}>
          {nodes.map((node, i) => {
            const Icon = node.icon
            const isSelected = selectedNode?.id === node.id

            return (
              <div key={node.id} style={{ display: 'flex', alignItems: 'center', position: 'relative' }}>
                {/* Node Box */}
                <div
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                  style={{
                    flex: 1,
                    padding: '16px 18px',
                    borderRadius: 14,
                    background: isSelected ? `${node.color}18` : `${node.color}08`,
                    border: `1.5px solid ${isSelected ? node.color : `${node.color}25`}`,
                    cursor: 'pointer',
                    transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: isSelected ? `0 0 20px ${node.color}25` : 'none',
                    position: 'relative',
                    zIndex: 2,
                  }}
                  onMouseEnter={e => {
                    if (!isSelected) {
                      e.currentTarget.style.background = `${node.color}14`
                      e.currentTarget.style.borderColor = `${node.color}45`
                      e.currentTarget.style.transform = 'translateY(-2px)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isSelected) {
                      e.currentTarget.style.background = `${node.color}08`
                      e.currentTarget.style.borderColor = `${node.color}25`
                      e.currentTarget.style.transform = ''
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 8,
                      background: `${node.color}18`,
                      border: `1px solid ${node.color}30`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Icon size={16} color={node.color} />
                    </div>
                    <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', color: node.color, letterSpacing: '0.06em' }}>
                      {node.type}
                    </span>
                  </div>

                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {node.label}
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                    {node.techs.map(t => (
                      <span key={t} className="mono-code" style={{ fontSize: 10, padding: '1px 5px' }}>
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Connecting Flow Arrow to Next Node */}
                {i < nodes.length - 1 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justify: 'center',
                    padding: '0 4px',
                    color: node.color,
                    zIndex: 1,
                  }}>
                    <ChevronRight size={18} opacity={0.6} />
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Selected Node Details Drawer */}
        {selectedNode && (
          <div style={{
            marginTop: 20,
            padding: '16px 20px',
            borderRadius: 12,
            background: 'rgba(0,0,0,0.3)',
            border: `1px solid ${selectedNode.color}35`,
            animation: 'fadeIn 0.3s ease both',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: selectedNode.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {selectedNode.label} Layer Inspection
                </span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2 }}
              >
                <X size={14} />
              </button>
            </div>

            <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 10 }}>
              {selectedNode.details}
            </p>

            {selectedNode.endpoints && selectedNode.endpoints.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {selectedNode.endpoints.map(ep => (
                  <span key={`${ep.method}-${ep.path}`} className="mono-code" style={{ fontSize: 11 }}>
                    <strong style={{ color: selectedNode.color }}>{ep.method}</strong> {ep.path}
                  </span>
                ))}
              </div>
            )}

            {selectedNode.modules && selectedNode.modules.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                {selectedNode.modules.map(mod => (
                  <span key={mod} className="mono-code" style={{ fontSize: 11 }}>
                    📁 {mod}/
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
