import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { ClusterProvider } from '@/context/ClusterContext';

export const metadata: Metadata = {
  title: 'WebSync AI — Distributed Computing Platform',
  description: 'Cross-platform distributed computing management dashboard and telemetry mesh',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#090d16] text-gray-100 min-h-screen flex antialiased">
        <ClusterProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
            <Header />
            <main className="flex-1 p-6 md:p-8 overflow-y-auto">{children}</main>
          </div>
        </ClusterProvider>
      </body>
    </html>
  );
}
