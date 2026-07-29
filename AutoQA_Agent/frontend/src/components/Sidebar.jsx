import { useState, useEffect } from 'react'
import { LayoutDashboard, History, Github, Zap, ChevronLeft, ChevronRight } from 'lucide-react'

export default function Sidebar({ activePage, onNavigate, historyCount = 0 }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true' } catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', collapsed) } catch {}
  }, [collapsed])

  const navItems = [
    { id: 'home',    label: 'Dashboard', icon: LayoutDashboard },
    { id: 'history', label: 'History',   icon: History, badge: historyCount },
  ]

  const sidebarWidth = collapsed ? 64 : 224

  return (
    <aside style={{
      width: sidebarWidth,
      flexShrink: 0,
      height: '100vh',
      position: 'sticky',
      top: 0,
      display: 'flex',
      flexDirection: 'column',
      background: '#0B1020',
      borderRight: '1px solid var(--border)',
      zIndex: 100,
      transition: 'width 0.25s cubic-bezier(0.4,0,0.2,1)',
      overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{
        padding: collapsed ? '24px 0 20px' : '24px 20px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        transition: 'padding 0.25s',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 10, overflow: 'hidden' }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9, flexShrink: 0,
            background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(59,130,246,0.35)',
          }}>
            <Zap size={17} color="#fff" fill="#fff" />
          </div>
          {!collapsed && (
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontWeight: 800, fontSize: 14, letterSpacing: '-0.02em', color: 'var(--text-primary)', lineHeight: 1, whiteSpace: 'nowrap' }}>
                AutoQA
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
                AGENT
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav style={{ padding: collapsed ? '12px 8px' : '12px 10px', flex: 1 }}>
        {navItems.map(({ id, label, icon: Icon, badge }) => {
          const isActive = activePage === id
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              title={collapsed ? label : undefined}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'flex-start',
                gap: collapsed ? 0 : 10,
                padding: collapsed ? '9px 0' : '9px 12px',
                borderRadius: 10,
                background: isActive ? 'rgba(59,130,246,0.12)' : 'transparent',
                border: isActive ? '1px solid rgba(59,130,246,0.2)' : '1px solid transparent',
                color: isActive ? '#3B82F6' : 'var(--text-secondary)',
                fontFamily: 'Inter, sans-serif',
                fontSize: 13, fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
                marginBottom: 2,
                textAlign: 'left',
                position: 'relative',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.035)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <Icon size={15} style={{ flexShrink: 0 }} />
              {!collapsed && <span style={{ flex: 1, whiteSpace: 'nowrap' }}>{label}</span>}
              {!collapsed && badge > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 700, minWidth: 18, height: 18,
                  borderRadius: 99, background: 'rgba(59,130,246,0.2)',
                  color: '#3B82F6', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', padding: '0 5px',
                }}>
                  {badge}
                </span>
              )}
              {collapsed && badge > 0 && (
                <span style={{
                  position: 'absolute', top: 6, right: 8,
                  width: 7, height: 7, borderRadius: '50%',
                  background: '#3B82F6',
                }} />
              )}
            </button>
          )
        })}
      </nav>

      {/* Toggle button */}
      <div style={{ padding: collapsed ? '10px 8px' : '10px', borderTop: '1px solid var(--border)' }}>
        <button
          onClick={() => setCollapsed(c => !c)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 8,
            padding: collapsed ? '8px 0' : '8px 12px',
            borderRadius: 10,
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            fontFamily: 'Inter, sans-serif',
            fontSize: 12, fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = 'rgba(59,130,246,0.08)'
            e.currentTarget.style.borderColor = 'rgba(59,130,246,0.2)'
            e.currentTarget.style.color = '#3B82F6'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.color = 'var(--text-muted)'
          }}
        >
          {collapsed ? <ChevronRight size={14} /> : <><ChevronLeft size={14} /><span>Collapse</span></>}
        </button>
      </div>

      {/* Footer */}
      {!collapsed && (
        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              color: 'var(--text-muted)', fontSize: 12, textDecoration: 'none',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text-secondary)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
          >
            <Github size={13} />
            <span>Open Source</span>
          </a>
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            Code-First · Local-First
          </div>
        </div>
      )}
    </aside>
  )
}
