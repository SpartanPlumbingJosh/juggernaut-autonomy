import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spartan Job Tracker",
  description: "Spartan Plumbing — Job Lifecycle Tracker",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-surface-0">
        {children}
      </body>
    </html>
  );
}