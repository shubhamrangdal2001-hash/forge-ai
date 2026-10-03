import "./globals.css";
import type { ReactNode } from "react";

export const metadata = { title: "Forge", description: "AI-native coding platform" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-forge-bg text-gray-200 antialiased">{children}</body>
    </html>
  );
}
