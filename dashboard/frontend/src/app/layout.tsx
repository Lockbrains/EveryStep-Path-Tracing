import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AppSidebar } from "@/components/AppSidebar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "EveryStep — Path Tracing × AI Agents",
  description:
    "Visualization dashboard for Monte Carlo–inspired agentic Art Bible generation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body
        className={`${inter.className} min-h-full bg-zinc-950 text-zinc-100 antialiased`}
      >
        <AppSidebar />
        <div className="min-h-full pl-64">{children}</div>
      </body>
    </html>
  );
}
