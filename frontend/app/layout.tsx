/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-11
 * License: MIT
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Garmin AI Coach",
  description: "Chat interface for Garmin training insights.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

