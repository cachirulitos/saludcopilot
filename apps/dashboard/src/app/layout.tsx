import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SaludCopilot — Dashboard",
  description: "Panel operativo en tiempo real para clínicas Salud Digna",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-surface-base text-content-primary">
        {/* Persistent sidebar */}
        <Sidebar
          clinicName="Clínica Demo"
          isConnected={false}
          alertCount={0}
        />

        {/* Main content — offset by sidebar width */}
        <div style={{ marginLeft: 240 }} className="flex flex-col min-h-screen">
          <TopBar pageTitle="Dashboard" isConnected={false} />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
