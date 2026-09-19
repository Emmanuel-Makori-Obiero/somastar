import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../app/providers/AuthProvider";
import { EDUVANCE_URL } from "../../services/links";
import "./AppLayout.css";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: "🏠" },
  { to: "/upload", label: "Upload Exam", icon: "📄" },
  { to: "/self-assessment", label: "Self Assessment", icon: "📊" },
  { to: "/skills", label: "Skills", icon: "✦" },
  { to: "/revision", label: "Revision", icon: "🧠" },
  { to: "/feed", label: "Video Feed", icon: "▶" },
];

export default function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand-mark">✦</span>
          <span className="app-brand-name">Somastar</span>
        </div>

        <nav className="app-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `app-nav-link${isActive ? " active" : ""}`
              }
            >
              <span className="app-nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
          <a
            className="app-nav-link app-nav-link-revise-more"
            href={EDUVANCE_URL}
          >
            <span className="app-nav-icon">↗</span>
            Revise more
          </a>
        </nav>

        <div className="app-sidebar-footer">
          <div className="app-user">
            <div className="app-user-avatar">
              {user?.name?.[0]?.toUpperCase() || "S"}
            </div>
            <div>
              <div className="app-user-name">{user?.name}</div>
              <button className="app-logout" onClick={logout}>
                Sign out
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
