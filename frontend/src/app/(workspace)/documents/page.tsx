import type { Metadata } from 'next'

import FeaturePlaceholder from '../../../components/FeaturePlaceholder'

export const metadata: Metadata = { title: 'Documents' }

export default function DocumentsPage() {
  return (
    <FeaturePlaceholder
      eyebrow="Research library"
      title="Documents"
      description="A future home for source material used in research workflows, with provenance visible alongside every extracted passage."
      plannedCapabilities={[
        'Upload and describe research documents',
        'Search document text and metadata',
        'Trace generated analysis back to its sources',
      ]}
    />
  )
}
