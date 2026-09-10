import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import '../index.css'
import '../App.css'

export const metadata: Metadata = {
  title: {
    default: 'Quant Research Dashboard',
    template: '%s | Quant Research Dashboard',
  },
  description:
    'A research and education workspace for deterministic A-share market analysis.',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
