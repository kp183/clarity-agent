import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Clarity — AI DevOps Copilot',
  description: 'Free AI-powered root cause analysis. Cut incident resolution time by 95%. Analyze production logs in 5 seconds instead of 4 hours.',
  openGraph: {
    title: 'Clarity — AI DevOps Copilot',
    description: 'Free AI-powered root cause analysis. Cut incident resolution time by 95%.',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
