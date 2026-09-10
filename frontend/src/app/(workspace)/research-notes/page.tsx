import type { Metadata } from 'next'

import FeaturePlaceholder from '../../../components/FeaturePlaceholder'

export const metadata: Metadata = { title: 'Research notes' }

export default function ResearchNotesPage() {
  return (
    <FeaturePlaceholder
      eyebrow="Research journal"
      title="Research notes"
      description="A future workspace for recording hypotheses, observations, and reproducible links to market data and scanner results."
      plannedCapabilities={[
        'Create structured research notes',
        'Link stocks, signals, and scanner runs',
        'Separate observed evidence from researcher interpretation',
      ]}
    />
  )
}
