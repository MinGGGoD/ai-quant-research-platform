import Link from 'next/link'

export default function WorkspaceNotFound() {
  return (
    <main className="feature-page">
      <section className="panel feature-card">
        <p className="section-kicker">Not found</p>
        <h1>This research route does not exist.</h1>
        <p>Check the stock exchange, symbol, or scanner-run identifier.</p>
        <Link className="secondary-link" href="/">
          Return to dashboard
        </Link>
      </section>
    </main>
  )
}
