import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TaxOps · Automatización Contable Colombia",
  description:
    "Procesa facturas electrónicas DIAN, prorrateo IVA Art. 490 ET, exógenas Formato 1003 y chatbot contable IA.",
  manifest: "/manifest.json",
  themeColor: "#1A3A5C",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "TaxOps" },
};

// Inline script injected before paint — avoids FOUC on dark mode
const themeScript = `
  (function() {
    try {
      var t = localStorage.getItem('taxops_theme');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      }
    } catch(e) {}
  })()
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        {/* eslint-disable-next-line @next/next/no-before-interactive-script-component */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#1A3A5C" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body className="font-sans bg-gray-50 text-gray-900 dark:bg-slate-900 dark:text-gray-100">
        {children}
      </body>
    </html>
  );
}
