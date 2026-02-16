import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import NavBar from "@/components/NavBar";
import { PortfolioProvider } from "@/context/PortfolioContext";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "S&P 500 Portfolio Dashboard",
  description: "Data-driven portfolio decision-making dashboard for S&P 500 stocks",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} antialiased bg-slate-950 text-slate-100 font-sans min-h-screen`}
      >
        <PortfolioProvider>
          <NavBar />
          <main className="mx-auto max-w-[1600px] px-4 py-6">
            {children}
          </main>
        </PortfolioProvider>
      </body>
    </html>
  );
}
