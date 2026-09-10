import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import App from '../../../../App'

interface ScannerRunPageProps {
  params: Promise<{ runId: string }>
}

export async function generateMetadata({
  params,
}: ScannerRunPageProps): Promise<Metadata> {
  const { runId } = await params
  return { title: `Scanner run ${runId}` }
}

export default async function ScannerRunPage({ params }: ScannerRunPageProps) {
  const { runId } = await params
  if (!runId.trim()) {
    notFound()
  }

  return <App key={runId} initialScannerRunId={runId} />
}
