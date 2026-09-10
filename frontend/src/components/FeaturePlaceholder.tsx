import Link from 'next/link'

interface FeaturePlaceholderProps {
  eyebrow: string
  title: string
  description: string
  plannedCapabilities: string[]
}

export default function FeaturePlaceholder({
  eyebrow,
  title,
  description,
  plannedCapabilities,
}: FeaturePlaceholderProps) {
  return (
    <main className="feature-page">
      <section className="panel feature-card">
        <p className="section-kicker">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <div className="feature-boundary">
          Phase 2 establishes this route and its server-rendered shell. Data
          contracts and editing workflows will be introduced in their dedicated
          migration phases.
        </div>
        <h2>Planned capabilities</h2>
        <ul>
          {plannedCapabilities.map((capability) => (
            <li key={capability}>{capability}</li>
          ))}
        </ul>
        <Link className="secondary-link" href="/">
          Return to dashboard
        </Link>
      </section>
    </main>
  )
}
