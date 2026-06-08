import type { Metadata } from 'next'
import { Inter, Source_Serif_4 } from 'next/font/google'
import './globals.css'
import { Sidebar } from '@/components/sidebar'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' })

const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  weight: ['400', '500'],
  style: ['normal', 'italic'],
  variable: '--font-display',
})

export const metadata: Metadata = {
  title: 'Lebanon NH — Admin',
  description: 'Internal admin dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${sourceSerif.variable} ${inter.className} flex h-screen overflow-hidden bg-background`}>
        <Sidebar />
        <main className="flex flex-1 flex-col min-w-0 overflow-auto">
          <div className="flex-1 px-6 py-6">
            {children}
          </div>
        </main>
      </body>
    </html>
  )
}
