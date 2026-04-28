import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Trading System Monitor",
  description: "Operator dashboard for the jlsprojects.com trading system.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
