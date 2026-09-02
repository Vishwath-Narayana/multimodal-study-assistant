import type { ReactNode } from "react";

const NAV_ITEMS = ["Library", "Chat", "Study"] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text font-sans">
      <header className="flex items-center justify-between border-b border-border px-8 py-4">
        <span className="text-sm font-medium tracking-wide text-text">
          Study Assistant
        </span>
        <nav className="flex gap-6">
          {NAV_ITEMS.map((item) => (
            <span
              key={item}
              className="text-sm text-text-muted transition-colors hover:text-text"
            >
              {item}
            </span>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-8 py-12">{children}</main>
    </div>
  );
}
