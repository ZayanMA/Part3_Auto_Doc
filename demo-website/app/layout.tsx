import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AutoDoc — AI Documentation Generator',
  description: 'Generate, review, and publish documentation automatically from your codebase',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">{children}</body>
    </html>
  )
}
