import { NavLink, Outlet } from "react-router-dom";

const MODES = [
  { to: "summary", label: "Summary" },
  { to: "explain", label: "Explain" },
  { to: "compare", label: "Compare" },
  { to: "quiz", label: "Quiz" },
  { to: "mcq", label: "MCQ" },
  { to: "flashcards", label: "Flashcards" },
] as const;

export function StudyPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-text">Study workspace</h1>
        <p className="mt-1 text-sm text-text-muted">
          Generate grounded study material from your documents.
        </p>
      </div>
      <nav aria-label="Study modes" className="flex flex-wrap gap-1 border-b border-border pb-2">
        {MODES.map((mode) => (
          <NavLink
            key={mode.to}
            to={mode.to}
            className={({ isActive }) =>
              `rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                isActive ? "bg-surface text-text" : "text-text-muted hover:text-text"
              }`
            }
          >
            {mode.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
