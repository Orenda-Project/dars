import type { Metadata } from "next";
import { Cormorant_Garamond, Geist_Mono, Lora, Noto_Nastaliq_Urdu } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const lora = Lora({
  variable: "--font-lora",
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin"],
  weight: ["600", "700"],
});

const notoNastaliq = Noto_Nastaliq_Urdu({
  variable: "--font-nastaliq",
  subsets: ["arabic"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "Dars — Lesson plan infrastructure",
  description:
    "Dars gives edtech teams a complete API for generating, storing, and rendering curriculum-aligned lesson plans — powered by AI, built to scale.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${lora.variable} ${geistMono.variable} ${notoNastaliq.variable} ${cormorant.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              fontFamily: "var(--font-lora), Georgia, serif",
              background: "#1c1410",
              color: "#faf7f2",
              border: "1px solid #2e2420",
            },
          }}
        />
      </body>
    </html>
  );
}
