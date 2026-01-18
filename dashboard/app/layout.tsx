import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'JUGGERNAUT Dashboard',
  description: 'Executive Dashboard for JUGGERNAUT Autonomous System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
