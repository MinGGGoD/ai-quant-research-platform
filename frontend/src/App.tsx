import './App.css'

function App() {
  return (
    <main className="app-shell">
      <p className="eyebrow">Phase 1 foundation</p>
      <h1>AI Quant Research Platform</h1>
      <p className="summary">
        A local research environment for daily market data, technical signals,
        and explainable quantitative workflows.
      </p>
      <section className="status-card" aria-labelledby="setup-status">
        <h2 id="setup-status">Development setup ready</h2>
        <p>
          Dashboard features will be implemented in Phase 6 after the data,
          scanner, and API foundations are complete.
        </p>
      </section>
      <p className="boundary">
        Research and education only. No broker connections or trade execution.
      </p>
    </main>
  )
}

export default App
