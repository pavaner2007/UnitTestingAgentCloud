import { useState, useMemo, useCallback } from 'react'
import { GitBranch, Database, Globe, ChevronDown, ChevronRight, Search, Filter, ZoomIn, ZoomOut, RefreshCw, Info, Layers } from 'lucide-react'

const NODE_COLORS = {
  api_endpoint: { bg: '#3b82f6', border: '#1d4ed8', text: '#fff', icon: '🌐' },
  function:     { bg: '#8b5cf6', border: '#6d28d9', text: '#fff', icon: '⚙️' },
  class:        { bg: '#a78bfa', border: '#7c3aed', text: '#fff', icon: '🏛️' },
  db_call:      { bg: '#f59e0b', border: '#d97706', text: '#fff', icon: '🗄️' },
  external_http:{ bg: '#ef4444', border: '#b91c1c', text: '#fff', icon: '🌍' },
  module:       { bg: '#6b7280', border: '#4b5563', text: '#fff', icon: '📦' },
}

function ConfidenceBadge({ score }) {
  const pct = Math.round((score || 0) * 100)
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700, color, background: color + '22',
      border: `1px solid ${color}55`, borderRadius: '4px', padding: '1px 5px',
    }}>
      {pct}%
    </span>
  )
}

function FlowNode({ node, isSelected, onClick }) {
  const colors = NODE_COLORS[node.node_type] || NODE_COLORS.function
  return (
    <div
      onClick={() => onClick(node)}
      style={{
        background: isSelected ? colors.bg : colors.bg + 'cc',
        border: `2px solid ${isSelected ? colors.border : colors.bg}`,
        borderRadius: '10px', padding: '8px 14px', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: '8px',
        boxShadow: isSelected ? `0 0 0 3px ${colors.bg}55` : '0 2px 8px rgba(0,0,0,0.3)',
        transition: 'all 0.2s', minWidth: '180px', maxWidth: '260px',
        transform: isSelected ? 'scale(1.04)' : 'scale(1)',
      }}
    >
      <span style={{ fontSize: '16px' }}>{colors.icon}</span>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, color: colors.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {node.label}
        </div>
        <div style={{ fontSize: '10px', color: colors.text + 'bb', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {node.file_path?.split('/').slice(-1)[0] || ''}
          {node.line_number ? `:${node.line_number}` : ''}
        </div>
      </div>
      <ConfidenceBadge score={node.confidence} />
    </div>
  )
}

function FlowArrow() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '2px 0' }}>
      <div style={{ width: '2px', height: '24px', background: 'var(--border-subtle)', margin: '0 auto' }} />
      <span style={{ fontSize: '10px', color: 'var(--text-muted)', position: 'absolute', left: '50%', transform: 'translateX(-50%)' }}>↓</span>
    </div>
  )
}

// Render a single flow as a vertical chain
function FlowChain({ flow, onSelectNode, selectedNodeId }) {
  // Build a simple linear layout: root → direct children → DB/HTTP leaves
  const rootNode = flow.nodes.find(n => n.node_type === 'api_endpoint') || flow.nodes[0]
  if (!rootNode) return null

  // Build adjacency from edges
  const childMap = {}
  for (const edge of (flow.edges || [])) {
    if (!childMap[edge.from_id]) childMap[edge.from_id] = []
    childMap[edge.from_id].push(edge.to_id)
  }

  const nodeById = {}
  for (const n of flow.nodes) nodeById[n.id] = n

  // BFS render order (up to 12 nodes for display)
  const renderOrder = []
  const visited = new Set()
  const queue = [rootNode.id]
  while (queue.length && renderOrder.length < 12) {
    const id = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    if (nodeById[id]) renderOrder.push(nodeById[id])
    for (const child of (childMap[id] || [])) {
      if (!visited.has(child)) queue.push(child)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0', padding: '8px 0' }}>
      {renderOrder.map((node, idx) => (
        <div key={node.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <FlowNode
            node={node}
            isSelected={selectedNodeId === node.id}
            onClick={onSelectNode}
          />
          {idx < renderOrder.length - 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '2px 0' }}>
              <div style={{ width: '2px', height: '16px', background: 'var(--border-subtle)' }} />
              <div style={{ width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: '7px solid var(--border-subtle)' }} />
            </div>
          )}
        </div>
      ))}
      {flow.nodes.length > 12 && (
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
          +{flow.nodes.length - 12} more nodes
        </div>
      )}
    </div>
  )
}

export default function ExecutionFlowTab({ analysisId, report }) {
  const [selectedFlowIdx, setSelectedFlowIdx] = useState(0)
  const [selectedNode, setSelectedNode] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  // Get flows from report
  const allFlows = useMemo(() => {
    return (report?.execution_flow_data || [])
  }, [report])

  // Filter flows by search
  const filteredFlows = useMemo(() => {
    if (!searchQuery) return allFlows
    const q = searchQuery.toLowerCase()
    return allFlows.filter(f => (f.entry_point || '').toLowerCase().includes(q))
  }, [allFlows, searchQuery])

  const currentFlow = filteredFlows[selectedFlowIdx]

  // Filter nodes by type
  const displayNodes = useMemo(() => {
    if (!currentFlow) return []
    if (typeFilter === 'all') return currentFlow.nodes || []
    return (currentFlow.nodes || []).filter(n => n.node_type === typeFilter)
  }, [currentFlow, typeFilter])

  if (!allFlows.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '300px', gap: '12px' }}>
        <div style={{ fontSize: '48px' }}>🔍</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '16px' }}>No execution flow data available.</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Re-analyze the repository to generate execution flow graphs.</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #1e1b4b, #312e81)',
        borderRadius: '12px', padding: '16px 20px',
        display: 'flex', alignItems: 'center', gap: '12px',
        border: '1px solid #4338ca55',
      }}>
        <div style={{ fontSize: '32px' }}>🔀</div>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: '#e0e7ff' }}>Execution Flow Visualizer</div>
          <div style={{ fontSize: '13px', color: '#a5b4fc' }}>
            {allFlows.length} API endpoint flows traced via static AST analysis
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '16px' }}>
          {[
            { label: 'Flows', value: allFlows.length, color: '#818cf8' },
            { label: 'Avg Depth', value: Math.round(allFlows.reduce((s, f) => s + (f.execution_depth || 0), 0) / allFlows.length), color: '#34d399' },
          ].map(m => (
            <div key={m.label} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '22px', fontWeight: 800, color: m.color }}>{m.value}</div>
              <div style={{ fontSize: '11px', color: '#c7d2fe' }}>{m.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr 260px', gap: '16px', minHeight: '520px' }}>

        {/* Left: Entry Point List */}
        <div style={{
          background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                value={searchQuery}
                onChange={e => { setSearchQuery(e.target.value); setSelectedFlowIdx(0); setSelectedNode(null) }}
                placeholder="Search entry points…"
                style={{
                  width: '100%', padding: '7px 10px 7px 30px', borderRadius: '8px', fontSize: '12px',
                  background: 'var(--bg-app)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
            {filteredFlows.map((flow, idx) => {
              const [method, ...pathParts] = (flow.entry_point || '').split(' ')
              const path = pathParts.join(' ')
              const isActive = idx === selectedFlowIdx
              const methodColors = {
                GET: '#22c55e', POST: '#3b82f6', PUT: '#f59e0b',
                DELETE: '#ef4444', PATCH: '#8b5cf6',
              }
              return (
                <div
                  key={idx}
                  onClick={() => { setSelectedFlowIdx(idx); setSelectedNode(null) }}
                  style={{
                    padding: '8px 10px', borderRadius: '8px', cursor: 'pointer', marginBottom: '4px',
                    background: isActive ? 'var(--bg-hover)' : 'transparent',
                    border: isActive ? '1px solid var(--border-subtle)' : '1px solid transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{
                      fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px',
                      background: (methodColors[method] || '#6b7280') + '22',
                      color: methodColors[method] || '#6b7280',
                      border: `1px solid ${(methodColors[method] || '#6b7280')}44`,
                      flexShrink: 0,
                    }}>
                      {method}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {path}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)' }}>
                    <span>⬡ {flow.nodes?.length || 0} nodes</span>
                    <span>{flow.db_operations_count > 0 ? `🗄 ${flow.db_operations_count} DB` : ''}</span>
                    <span>{flow.external_http_calls_count > 0 ? `🌍 ${flow.external_http_calls_count} HTTP` : ''}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Center: Flow Diagram */}
        <div style={{
          background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          {/* Type filter toolbar */}
          <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
            <Filter size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
            {['all', 'api_endpoint', 'function', 'class', 'db_call', 'external_http'].map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                style={{
                  padding: '3px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600,
                  cursor: 'pointer', transition: 'all 0.15s',
                  background: typeFilter === t ? '#3b82f6' : 'var(--bg-app)',
                  color: typeFilter === t ? '#fff' : 'var(--text-muted)',
                  border: typeFilter === t ? '1px solid #2563eb' : '1px solid var(--border-subtle)',
                }}
              >
                {t === 'all' ? 'All' : t.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </button>
            ))}
          </div>

          {/* Flow content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', justifyContent: 'center' }}>
            {currentFlow ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0', width: '100%', maxWidth: '420px' }}>
                <div style={{ textAlign: 'center', marginBottom: '16px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {currentFlow.entry_point}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Confidence: {Math.round((currentFlow.confidence_score || 0) * 100)}% · Depth: {currentFlow.execution_depth || 0}
                  </div>
                </div>
                <FlowChain
                  flow={{ ...currentFlow, nodes: typeFilter === 'all' ? currentFlow.nodes : displayNodes }}
                  onSelectNode={setSelectedNode}
                  selectedNodeId={selectedNode?.id}
                />
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', margin: 'auto', fontSize: '13px' }}>
                Select an entry point to view its execution flow.
              </div>
            )}
          </div>

          {/* Legend */}
          <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {Object.entries(NODE_COLORS).map(([type, colors]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '3px', background: colors.bg }} />
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                  {colors.icon} {type.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Node Details */}
        <div style={{
          background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border-subtle)', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
            <Info size={14} style={{ marginRight: '6px', verticalAlign: 'text-bottom' }} />
            Node Details
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
            {selectedNode ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '24px' }}>{NODE_COLORS[selectedNode.node_type]?.icon}</span>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{selectedNode.label}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{selectedNode.node_type.replace('_', ' ')}</div>
                  </div>
                </div>
                {[
                  { label: 'File', value: selectedNode.file_path },
                  { label: 'Line', value: selectedNode.line_number ? `#${selectedNode.line_number}` : null },
                  { label: 'Confidence', value: <ConfidenceBadge score={selectedNode.confidence} /> },
                  ...(selectedNode.metadata?.class ? [{ label: 'Class', value: selectedNode.metadata.class }] : []),
                  ...(selectedNode.metadata?.db_operation ? [{ label: 'DB Op', value: selectedNode.metadata.db_operation }] : []),
                  ...(selectedNode.metadata?.http_call ? [{ label: 'HTTP', value: selectedNode.metadata.http_call }] : []),
                ].filter(r => r.value !== null && r.value !== undefined).map(row => (
                  <div key={row.label} style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{row.label}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px', wordBreak: 'break-all' }}>{row.value}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', paddingTop: '40px' }}>
                Click a node in the flow diagram to see its details.
              </div>
            )}
          </div>

          {/* Current flow stats */}
          {currentFlow && (
            <div style={{ padding: '12px', borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Flow Stats</div>
              {[
                { icon: '⬡', label: 'Total Nodes', value: currentFlow.nodes?.length || 0 },
                { icon: '↔️', label: 'Transitions', value: currentFlow.edges?.length || 0 },
                { icon: '📏', label: 'Depth', value: currentFlow.execution_depth || 0 },
                { icon: '🗄️', label: 'DB Ops', value: currentFlow.db_operations_count || 0 },
                { icon: '🌍', label: 'HTTP Calls', value: currentFlow.external_http_calls_count || 0 },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: '12px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{s.icon} {s.label}</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{s.value}</span>
                </div>
              ))}
              {currentFlow.exceptions_handled?.length > 0 && (
                <div style={{ marginTop: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Exceptions Handled</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {currentFlow.exceptions_handled.map(e => (
                      <span key={e} style={{ fontSize: '10px', padding: '2px 6px', background: '#ef444422', color: '#ef4444', borderRadius: '4px', border: '1px solid #ef444444' }}>
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
