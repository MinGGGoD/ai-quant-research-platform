import Link from 'next/link'
import type { ReactNode } from 'react'

interface SiteShellProps {
  children: ReactNode
}

export default function SiteShell({ children }: SiteShellProps) {
  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="eyebrow">A-share research workspace</p>
          <Link className="brand-link" href="/">
            Quant Research Dashboard
          </Link>
        </div>
        <div className="topbar-actions">
          <nav className="primary-nav" aria-label="Primary navigation">
            <Link href="/">Dashboard</Link>
            <Link href="/documents">Documents</Link>
            <Link href="/research-notes">Research notes</Link>
          </nav>
          <div className="research-boundary">
            <span className="status-dot" aria-hidden="true" />
            Research and education only
          </div>
        </div>
      </header>

      {children}

      <footer>
        Technical signals describe deterministic historical conditions. They are
        not investment recommendations or trading instructions.
      </footer>
    </div>
  )
}
