import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { ResearchUseOnlyBanner } from "@/components/ResearchUseOnlyBanner";

export const metadata: Metadata = {
  title: "Lulan DICOM MVP",
  description: "Research-only DICOM analysis MVP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <ResearchUseOnlyBanner />
        <header className="border-b bg-white px-4 py-2 flex items-center justify-between">
          <Link href="/worklist" className="font-semibold text-sm tracking-tight">
            Lulan DICOM <span className="text-warn-700 font-normal">(MVP · research only)</span>
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link href="/worklist" className="hover:underline">
              Worklist
            </Link>
            <Link href="/admin/audit" className="hover:underline">
              Audit
            </Link>
            <Link href="/login" className="hover:underline">
              Sign in
            </Link>
          </nav>
        </header>
        <main className="flex-1 px-4 py-4">{children}</main>
        <footer className="border-t bg-white px-4 py-2 text-[10px] text-gray-500">
          Generated outputs require licensed radiologist review and signature before clinical use.
        </footer>
      </body>
    </html>
  );
}
