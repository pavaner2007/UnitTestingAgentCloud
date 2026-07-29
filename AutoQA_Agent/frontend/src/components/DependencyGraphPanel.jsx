import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import * as d3Force from 'd3-force'
import { Network, GitFork, RefreshCw, Layers, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

/* ── Non-code file filter ── */
const SKIP_EXTENSIONS = new Set([
  '.css', '.scss', '.sass', '.less', '.styl',
  '.json', '.md', '.txt', '.yml', '.yaml', '.toml',
  '.env', '.gitignore', '.gitattributes', '.editorconfig',
  '.svg', '.png', '.jpg', '.jpeg', '.ico', '.woff', '.ttf', '.eot',
  '.lock', '.sum', '.mod', '.map',
])
function isCodeFile(file) {
  const last = file.split('.').pop() || ''
  return !SKIP_EXTENSIONS.has('.' + last.toLowerCase())
}

/* Estimate rendered text width (monospace ~7px/char at font-size 9) */
const CHAR_W = 7

/* Canvas logical dimensions — large internal space, viewport clips it */
const W = 1400
const H = 900

function StatCard({ icon: Icon, label, value, color = 'var(--accent-teal)' }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 12, padding: '18px 22px', flex: 1, minWidth: 140,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Icon size={13} color={color} />
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {label}
        </span>
      </div>
      <div style={{
        fontSize: typeof value === 'number' ? 28 : 14,
        fontWeight: 800, color: 'var(--text-primary)',
        fontFamily: typeof value === 'number' ? 'Inter, sans-serif' : 'JetBrains Mono, monospace',
        wordBreak: 'break-all', lineHeight: 1,
      }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function DependencyGraphPanel({ dependencyGraph }) {
  const [selectedNode, setSelectedNode] = useState(null)
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const svgRef = useRef(null)
  const containerRef = useRef(null)

  // Pan & zoom state
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 })
  const dragStart = useRef(null)
  const transformRef = useRef({ x: 0, y: 0, k: 1 })

  // Keep ref in sync with state
  useEffect(() => { transformRef.current = transform }, [transform])

  const rawGraph = dependencyGraph || { nodes: [], edges: [], cycles: [], most_depended_on: null }

  /* Cyclic file set */
  const cyclicFiles = useMemo(() => {
    const s = new Set()
    for (const c of rawGraph.cycles || []) for (const f of c) s.add(f)
    return s
  }, [rawGraph.cycles])

  /* Filter: code-only, connected nodes */
  const { codeNodes, codeEdges } = useMemo(() => {
    const codeFileSet = new Set(
      (rawGraph.nodes || []).filter(n => isCodeFile(n.file)).map(n => n.file)
    )
    const filteredEdges = (rawGraph.edges || []).filter(e => {
      const from = e.from_file || e.from
      const to   = e.to_file   || e.to
      return codeFileSet.has(from) && codeFileSet.has(to)
    })
    const connectedFiles = new Set()
    for (const e of filteredEdges) {
      connectedFiles.add(e.from_file || e.from)
      connectedFiles.add(e.to_file   || e.to)
    }
    const filteredNodes = (rawGraph.nodes || []).filter(n =>
      codeFileSet.has(n.file) && (connectedFiles.has(n.file) || (n.dependency_count || 0) > 0)
    )
    return { codeNodes: filteredNodes, codeEdges: filteredEdges }
  }, [rawGraph])

  /* Stats */
  const numNodes    = codeNodes.length
  const numEdges    = codeEdges.length
  const numCycles   = rawGraph.cycles?.length || 0
  const mostDepended = rawGraph.most_depended_on || '—'

  /* ── d3 force layout ── */
  useEffect(() => {
    if (codeNodes.length === 0) { setNodes([]); setLinks([]); return }

    const CIRCLE_R = 8

    const simNodes = codeNodes.map((n, idx) => {
      const label   = n.file.split('/').pop()
      const textW   = label.length * CHAR_W
      const dep     = n.dependency_count || 0
      const r       = CIRCLE_R + Math.min(dep * 2, 14)
      return {
        id:       n.file,
        label,
        file:     n.file,
        dep,
        isCyclic: cyclicFiles.has(n.file),
        r,
        textW,
        idx,
        // Collision radius: circle radius + full text half-width + generous padding
        collideR: r + textW / 2 + 22,
      }
    })

    const nodeMap = new Map(simNodes.map(n => [n.id, n]))

    const simLinks = codeEdges
      .map(e => ({
        source:   nodeMap.get(e.from_file || e.from),
        target:   nodeMap.get(e.to_file   || e.to),
        isCyclic: cyclicFiles.has(e.from_file || e.from) && cyclicFiles.has(e.to_file || e.to),
      }))
      .filter(l => l.source && l.target)

    const sim = d3Force.forceSimulation(simNodes)
      .force('link',
        d3Force.forceLink(simLinks)
          .id(d => d.id)
          // Scale edge distance by label widths so labels have room to breathe
          .distance(d => 120 + (d.source.textW + d.target.textW) / 2 + d.source.r + d.target.r)
          .strength(0.3)
      )
      // Much stronger repulsion to push dense clusters apart
      .force('charge', d3Force.forceManyBody().strength(-1200).distanceMin(30).distanceMax(600))
      .force('center', d3Force.forceCenter(W / 2, H / 2).strength(0.2))
      // Label-aware collision: prevents circles AND their text from overlapping
      .force('collide', d3Force.forceCollide().radius(d => d.collideR).strength(1.0).iterations(6))
      // Gentle centering springs to prevent stray nodes from flying to infinity
      .force('x', d3Force.forceX(W / 2).strength(0.04))
      .force('y', d3Force.forceY(H / 2).strength(0.04))
      .stop()

    // More ticks for larger graphs to reach equilibrium
    const tickCount = Math.min(800 + codeNodes.length * 4, 1200)
    for (let i = 0; i < tickCount; ++i) sim.tick()

    /* Clamp inside logical canvas */
    const padH = 80, padV = 60
    for (const n of simNodes) {
      n.x = Math.max(padH + n.r, Math.min(W - padH - n.r, n.x))
      n.y = Math.max(padV + n.r, Math.min(H - padV - n.r, n.y))
    }

    setNodes([...simNodes])
    setLinks([...simLinks])

    // Auto-fit: scale/pan so the whole graph fills the viewport
    requestAnimationFrame(() => {
      const container = containerRef.current
      if (!container || simNodes.length === 0) return
      const vw = container.clientWidth
      const vh = container.clientHeight || 500
      const xs = simNodes.map(n => n.x)
      const ys = simNodes.map(n => n.y)
      const minX = Math.min(...xs) - 60
      const maxX = Math.max(...xs) + 60
      const minY = Math.min(...ys) - 60
      const maxY = Math.max(...ys) + 60
      const gw = maxX - minX
      const gh = maxY - minY
      const k  = Math.min(vw / gw, vh / gh, 1.4)
      const cx = vw / 2 - (minX + gw / 2) * k
      const cy = vh / 2 - (minY + gh / 2) * k
      setTransform({ x: cx, y: cy, k })
    })
  }, [codeNodes, codeEdges, cyclicFiles])

  /* ── Pan/zoom handlers ── */
  const onWheel = useCallback((e) => {
    e.preventDefault()
    const delta = e.deltaY < 0 ? 1.12 : 0.89
    const rect  = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    setTransform(prev => {
      const k = Math.max(0.1, Math.min(5, prev.k * delta))
      // Zoom toward mouse position
      const x = mx - (mx - prev.x) * (k / prev.k)
      const y = my - (my - prev.y) * (k / prev.k)
      return { x, y, k }
    })
  }, [])

  const onMouseDown = useCallback((e) => {
    if (e.button !== 0) return
    dragStart.current = {
      mx: e.clientX,
      my: e.clientY,
      tx: transformRef.current.x,
      ty: transformRef.current.y,
    }
  }, [])

  const onMouseMove = useCallback((e) => {
    if (!dragStart.current) return
    const dx = e.clientX - dragStart.current.mx
    const dy = e.clientY - dragStart.current.my
    setTransform(prev => ({
      ...prev,
      x: dragStart.current.tx + dx,
      y: dragStart.current.ty + dy,
    }))
  }, [])

  const onMouseUp = useCallback(() => { dragStart.current = null }, [])

  const zoomIn  = () => setTransform(p => ({ ...p, k: Math.min(p.k * 1.25, 5) }))
  const zoomOut = () => setTransform(p => ({ ...p, k: Math.max(p.k * 0.8, 0.1) }))
  const resetView = () => {
    const container = containerRef.current
    if (!container || nodes.length === 0) return
    const vw = container.clientWidth
    const vh = container.clientHeight || 500
    const xs = nodes.map(n => n.x)
    const ys = nodes.map(n => n.y)
    const minX = Math.min(...xs) - 60
    const maxX = Math.max(...xs) + 60
    const minY = Math.min(...ys) - 60
    const maxY = Math.max(...ys) + 60
    const gw = maxX - minX
    const gh = maxY - minY
    const k  = Math.min(vw / gw, vh / gh, 1.4)
    const cx = vw / 2 - (minX + gw / 2) * k
    const cy = vh / 2 - (minY + gh / 2) * k
    setTransform({ x: cx, y: cy, k })
  }

  /* Register wheel listener (passive:false needed to call preventDefault) */
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [onWheel])

  if (!dependencyGraph || codeNodes.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 14, padding: '48px', textAlign: 'center', color: 'var(--text-muted)',
        animation: 'fadeSlideUp 0.45s ease both',
      }}>
        <Network size={32} style={{ margin: '0 auto 12px', opacity: 0.35 }} />
        <p style={{ fontSize: 14, fontWeight: 600 }}>No dependency graph data available</p>
        <p style={{ fontSize: 12, marginTop: 6 }}>The scanner runs on Python and JS/TS source files.</p>
      </div>
    )
  }

  const { x: tx, y: ty, k: tk } = transform

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, animation: 'fadeSlideUp 0.45s ease both' }}>

      {/* ── Stat bar ── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <StatCard icon={Network}    label="Nodes"            value={numNodes}    color="var(--accent-teal)" />
        <StatCard icon={GitFork}    label="Edges"            value={numEdges}    color="var(--accent-teal)" />
        <StatCard icon={RefreshCw}  label="Cycles"           value={numCycles}   color={numCycles > 0 ? '#EF4444' : 'var(--accent-teal)'} />
        <StatCard icon={Layers}     label="Most Depended On" value={mostDepended} color="var(--accent-teal)" />
      </div>

      {/* ── Graph canvas ── */}
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 14, overflow: 'hidden', position: 'relative',
      }}>
        {/* Legend + zoom controls */}
        <div style={{
          padding: '10px 18px', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent-teal)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Import Map
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width={14} height={14}><circle cx={7} cy={7} r={5} fill="rgba(170,190,220,0.18)" stroke="rgba(170,190,220,0.55)" strokeWidth={1.5}/></svg>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>File node (size = in-degree)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width={14} height={14}><circle cx={7} cy={7} r={5} fill="rgba(239,68,68,0.18)" stroke="#EF4444" strokeWidth={1.5}/></svg>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Circular import</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width={22} height={8}><line x1={0} y1={4} x2={22} y2={4} stroke="rgba(148,163,184,0.4)" strokeWidth={1.2} markerEnd="url(#leg-arr)"/><defs><marker id="leg-arr" viewBox="0 -3 6 6" markerWidth={3} markerHeight={3} refX={6} orient="auto"><path d="M0,-3L6,0L0,3" fill="rgba(148,163,184,0.6)"/></marker></defs></svg>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Import direction</span>
          </div>

          {/* Zoom toolbar */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              {Math.round(tk * 100)}%
            </span>
            {[
              { icon: ZoomOut, fn: zoomOut, title: 'Zoom out' },
              { icon: ZoomIn,  fn: zoomIn,  title: 'Zoom in'  },
              { icon: Maximize2, fn: resetView, title: 'Fit to screen' },
            ].map(({ icon: Icon, fn, title }) => (
              <button
                key={title}
                onClick={fn}
                title={title}
                style={{
                  background: 'rgba(14,21,37,0.7)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '5px 7px', cursor: 'pointer',
                  color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--accent-teal)'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
              >
                <Icon size={13} />
              </button>
            ))}
          </div>
        </div>

        {/* SVG viewport — pan via drag, zoom via wheel or buttons */}
        <div
          ref={containerRef}
          style={{ background: 'rgba(4,8,18,0.98)', overflow: 'hidden', cursor: dragStart.current ? 'grabbing' : 'grab', userSelect: 'none' }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          <svg
            ref={svgRef}
            width="100%"
            style={{ display: 'block', minHeight: 500 }}
            viewBox={`0 0 ${containerRef.current?.clientWidth || 900} 500`}
          >
            <defs>
              <marker id="dep-arr"   viewBox="0 -4 8 8" refX={24} refY={0} markerWidth={5} markerHeight={5} orient="auto">
                <path d="M0,-4L8,0L0,4" fill="rgba(148,163,184,0.5)" />
              </marker>
              <marker id="dep-arr-c" viewBox="0 -4 8 8" refX={24} refY={0} markerWidth={5} markerHeight={5} orient="auto">
                <path d="M0,-4L8,0L0,4" fill="#EF4444" />
              </marker>
              <filter id="dep-glow">
                <feGaussianBlur stdDeviation="3" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>

            {/* Transform group — all graph content lives inside this */}
            <g transform={`translate(${tx},${ty}) scale(${tk})`}>
              {/* Edges */}
              {links.map((l, i) => {
                const isHighlighted = selectedNode &&
                  (l.source.id === selectedNode.id || l.target.id === selectedNode.id)
                return (
                  <line
                    key={i}
                    x1={l.source.x} y1={l.source.y}
                    x2={l.target.x} y2={l.target.y}
                    stroke={l.isCyclic ? '#EF4444' : isHighlighted ? 'rgba(120,200,255,0.85)' : 'rgba(148,163,184,0.22)'}
                    strokeWidth={isHighlighted ? 1.8 : l.isCyclic ? 1.5 : 0.9}
                    strokeDasharray={l.isCyclic ? '4 3' : 'none'}
                    markerEnd={l.isCyclic ? 'url(#dep-arr-c)' : 'url(#dep-arr)'}
                  />
                )
              })}

              {/* Nodes */}
              {nodes.map(node => {
                const isSelected = selectedNode?.id === node.id
                const isHighlighted = selectedNode && (
                  isSelected ||
                  links.some(l =>
                    (l.source.id === selectedNode.id && l.target.id === node.id) ||
                    (l.target.id === selectedNode.id && l.source.id === node.id)
                  )
                )

                const circleFill = node.isCyclic
                  ? 'rgba(239,68,68,0.22)'
                  : isSelected
                    ? 'rgba(200,225,255,0.32)'
                    : 'rgba(170,190,220,0.13)'
                const circleStroke = node.isCyclic
                  ? '#EF4444'
                  : isSelected
                    ? 'rgba(200,225,255,1)'
                    : isHighlighted
                      ? 'rgba(120,200,255,0.8)'
                      : 'rgba(170,190,220,0.45)'

                /*
                 * Label staggering strategy:
                 * Primary axis: top half of canvas → label below; bottom half → label above.
                 * Secondary offset: alternate even/odd nodes by ±6px so adjacent nodes
                 * whose circles are at similar Y positions don't produce horizontally
                 * merged label baselines.
                 */
                const labelBelow  = node.y < H / 2
                const stagger     = (node.idx % 2 === 0) ? 0 : (labelBelow ? 6 : -6)
                const labelY      = labelBelow
                  ? node.r + 13 + stagger
                  : -(node.r + 5 + Math.abs(stagger))

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    onClick={(e) => { e.stopPropagation(); setSelectedNode(isSelected ? null : node) }}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      r={node.r}
                      fill={circleFill}
                      stroke={circleStroke}
                      strokeWidth={isSelected || node.isCyclic ? 2 : 1.2}
                      filter={node.dep >= 3 ? 'url(#dep-glow)' : undefined}
                      style={{ transition: 'all 0.18s' }}
                    />
                    {/* Invisible hit-area so small nodes are easier to click */}
                    <circle r={Math.max(node.r, 10)} fill="transparent" />
                    {/* Label — always outside the circle, staggered to avoid merging */}
                    <text
                      y={labelY}
                      textAnchor="middle"
                      fill={node.isCyclic ? '#F87171' : isSelected ? '#fff' : 'rgba(200,215,235,0.85)'}
                      fontSize={9}
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight={node.dep >= 3 ? 600 : 400}
                      pointerEvents="none"
                      style={{ userSelect: 'none' }}
                    >
                      {node.label}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        </div>

        {/* Selected node info bar */}
        {selectedNode && (
          <div style={{
            padding: '12px 20px', borderTop: '1px solid var(--border)',
            background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            animation: 'fadeIn 0.2s ease both',
          }}>
            <div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Selected:{' '}
              </span>
              <span className="mono-code" style={{ fontSize: 12, fontWeight: 700 }}>
                {selectedNode.file}
              </span>
              <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
                ({selectedNode.dep} dependent{selectedNode.dep !== 1 ? 's' : ''})
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {selectedNode.isCyclic && (
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                  background: 'rgba(239,68,68,0.15)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)',
                }}>
                  ⚠ Circular Import
                </span>
              )}
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}
              >×</button>
            </div>
          </div>
        )}
        <div style={{
          padding: '6px 18px',
          fontSize: 10, color: 'var(--text-muted)',
          borderTop: '1px solid var(--border)',
          background: 'rgba(0,0,0,0.2)',
        }}>
          Drag to pan · Scroll to zoom · Click a node to select
        </div>
      </div>
    </div>
  )
}
