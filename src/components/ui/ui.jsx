import "./ui.css";

export function Card({ children, className = "", ...props }) {
  return (
    <div className={`ui-card ${className}`} {...props}>
      {children}
    </div>
  );
}

export function Button({ children, variant = "primary", className = "", ...props }) {
  return (
    <button className={`ui-btn ui-btn-${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="ui-empty">
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function StatPill({ label, value }) {
  return (
    <div className="ui-stat-pill">
      <span className="ui-stat-value">{value}</span>
      <span className="ui-stat-label">{label}</span>
    </div>
  );
}

export function ErrorBanner({ message }) {
  if (!message) return null;
  return <div className="ui-error-banner">{message}</div>;
}
