import type { Metadata } from "next";
import localFont from "next/font/local";

import { Footer } from "@/components/layout/Footer";
import { Nav } from "@/components/layout/Nav";
import { Providers } from "@/components/layout/Providers";

import "@/styles/globals.css";

const anthropicSans = localFont({
  src: [
    {
      path: "../public/fonts/anthropic-sans-roman.woff2",
      style: "normal",
      weight: "300 800"
    },
    {
      path: "../public/fonts/anthropic-sans-italic.woff2",
      style: "italic",
      weight: "300 800"
    }
  ],
  variable: "--font-anthropic-sans",
  display: "swap"
});

const anthropicSerif = localFont({
  src: [
    {
      path: "../public/fonts/anthropic-serif-roman.woff2",
      style: "normal",
      weight: "300 800"
    },
    {
      path: "../public/fonts/anthropic-serif-italic.woff2",
      style: "italic",
      weight: "300 800"
    }
  ],
  variable: "--font-anthropic-serif",
  display: "swap"
});

const anthropicMono = localFont({
  src: [
    {
      path: "../public/fonts/anthropic-mono-roman.woff2",
      style: "normal",
      weight: "300 800"
    },
    {
      path: "../public/fonts/anthropic-mono-italic.woff2",
      style: "italic",
      weight: "300 800"
    }
  ],
  variable: "--font-anthropic-mono",
  display: "swap"
});

export const metadata: Metadata = {
  metadataBase: new URL("https://evalledger.dev"),
  title: {
    default: "EvalLedger",
    template: "%s · EvalLedger"
  },
  description: "The open registry for AI benchmark provenance.",
  openGraph: {
    title: "EvalLedger",
    description: "The open registry for AI benchmark provenance.",
    url: "https://evalledger.dev",
    siteName: "EvalLedger",
    type: "website"
  },
  twitter: {
    card: "summary_large_image",
    title: "EvalLedger",
    description: "The open registry for AI benchmark provenance."
  },
  robots: {
    index: true,
    follow: true
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${anthropicSans.variable} ${anthropicSerif.variable} ${anthropicMono.variable} site-shell`}
      >
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:border focus:bg-[var(--surface)] focus:px-4 focus:py-2 focus:text-[14px] focus:text-[var(--text)]"
          style={{ borderColor: "var(--border)" }}
        >
          Skip to content
        </a>
        <Providers>
          <Nav />
          <main id="main-content">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
