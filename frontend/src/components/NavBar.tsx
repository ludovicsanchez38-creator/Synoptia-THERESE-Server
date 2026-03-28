import { useLocation, Link } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

const navLinks = [
  { to: "/chat", label: "Chat" },
  { to: "/tasks", label: "T\u00e2ches" },
  { to: "/skills", label: "Skills" },
  { to: "/crm", label: "Contacts" },
  { to: "/board", label: "Board" },
];

export default function NavBar() {
  const { user, logout } = useAuthStore();
  const location = useLocation();

  return (
    <header className="flex items-center justify-between px-4 md:px-6 py-3 border-b border-slate-800 shrink-0">
      <div className="flex items-center gap-4">
        <Link
          to="/chat"
          className="text-lg font-bold text-[var(--color-cyan)] hover:opacity-80 transition-opacity"
        >
          Th&eacute;r&egrave;se
        </Link>
        {user?.org_name && (
          <span className="text-xs text-[var(--color-muted)] bg-slate-800 px-2 py-0.5 rounded hidden sm:inline">
            {user.org_name}
          </span>
        )}
        <nav className="hidden md:flex items-center gap-1 ml-2">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              data-testid={`nav-link-${link.to.replace("/", "")}`}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                location.pathname === link.to ||
                location.pathname.startsWith(link.to + "/")
                  ? "bg-slate-800 text-[var(--color-cyan)]"
                  : "text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-slate-800/50"
              }`}
            >
              {link.label}
            </Link>
          ))}
          {user?.role === "admin" && (
            <Link
              to="/admin"
              data-testid="nav-link-admin"
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                location.pathname.startsWith("/admin")
                  ? "bg-slate-800 text-[var(--color-cyan)]"
                  : "text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-slate-800/50"
              }`}
            >
              Admin
            </Link>
          )}
        </nav>
      </div>
      <div className="flex items-center gap-4">
        {/* Navigation mobile */}
        <div className="flex md:hidden items-center gap-2">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                location.pathname === link.to
                  ? "bg-slate-800 text-[var(--color-cyan)]"
                  : "text-[var(--color-muted)]"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <span className="text-sm text-[var(--color-muted)] hidden sm:inline">
          {user?.name}
        </span>
        <button
          onClick={logout}
          className="text-xs text-[var(--color-muted)] hover:text-red-400 transition-colors"
        >
          D&eacute;connexion
        </button>
      </div>
    </header>
  );
}
