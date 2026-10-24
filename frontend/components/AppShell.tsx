"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import DataBadge from "./DataBadge";
import Onboarding from "./Onboarding";
import ThemeToggle from "./ThemeToggle";
import { useProfile } from "@/lib/profile";

const TABS = [
  { href: "/build", label: "Build", icon: "▦" },
  { href: "/week", label: "Week", icon: "▤" },
  { href: "/briefing", label: "Briefing", icon: "☰" },
  { href: "/eat", label: "Eat", icon: "◒" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { profile, ready } = useProfile();
  const [editing, setEditing] = useState(false);
  const showOnboarding = ready && (!profile || editing);

  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-10 focus:bg-background focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          <span className="text-lg font-bold text-accent">Compass</span>
          <div className="flex-1">
            <DataBadge />
          </div>
          {profile && !editing && (
            <button type="button" onClick={() => setEditing(true)} className="rounded border border-line bg-surface px-3 py-1.5 text-sm">
              <span aria-hidden="true">✎</span> Edit profile
            </button>
          )}
          <ThemeToggle />
        </div>
        <nav aria-label="Main" className="mx-auto max-w-5xl px-4">
          <ul className="flex gap-1">
            {TABS.map((t) => {
              const active = path === t.href;
              return (
                <li key={t.href}>
                  <Link
                    href={t.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex items-center gap-1.5 border-b-4 px-4 py-2 text-sm font-medium ${
                      active ? "border-accent text-accent" : "border-transparent hover:bg-surface"
                    }`}
                  >
                    <span aria-hidden="true">{t.icon}</span> {t.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-6">
        {!ready ? null : showOnboarding ? (
          <Onboarding initial={profile} onDone={() => setEditing(false)} onCancel={profile ? () => setEditing(false) : undefined} />
        ) : (
          children
        )}
      </main>
    </>
  );
}
