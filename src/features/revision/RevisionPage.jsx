import { useEffect, useState } from "react";
import { revisionApi } from "../../services/api";
import { EDUVANCE_URL } from "../../services/links";
import {
  Card,
  Button,
  EmptyState,
  ErrorBanner,
} from "../../components/ui/ui.jsx";
import "./RevisionPage.css";

const FILTERS = [
  { value: "pending", label: "To revise" },
  { value: "reviewed", label: "Reviewed" },
  { value: "mastered", label: "Mastered" },
];

export default function RevisionPage() {
  const [filter, setFilter] = useState("pending");
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    revisionApi
      .list(filter)
      .then((data) => {
        if (!cancelled) {
          setItems(data);
          setError("");
        }
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [filter]);

  async function move(item, status) {
    setError("");
    try {
      await revisionApi.setStatus(item.id, status);
      setItems((list) => list.filter((i) => i.id !== item.id)); // it now belongs to another tab
    } catch (err) {
      setError(err.message);
    }
  }

  function changeFilter(next) {
    setItems(null);
    setFilter(next);
  }

  return (
    <div className="revision-page">
      <div className="revision-header">
        <div>
          <h1>Revision</h1>
          <p>Questions worth revisiting, pulled from your analysed exams.</p>
        </div>
        <a className="revision-more-link" href={EDUVANCE_URL}>
          <Button>Revise more</Button>
        </a>
      </div>

      <div className="revision-tabs" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            role="tab"
            aria-selected={filter === f.value}
            className={`revision-tab${filter === f.value ? " active" : ""}`}
            onClick={() => changeFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <ErrorBanner message={error} />

      {items === null ? (
        !error && <p>Loading revision material…</p>
      ) : items.length === 0 ? (
        <EmptyState
          title={
            filter === "pending"
              ? "Nothing to revise right now"
              : "Nothing here yet"
          }
          description={
            filter === "pending"
              ? "Questions you missed or only partly got will show up here after an exam is analysed."
              : "Items you mark as reviewed or mastered will appear in this tab."
          }
        />
      ) : (
        <div className="revision-list">
          {items.map((item) => (
            <Card key={item.id} className="revision-item">
              <div className="revision-item-header">
                <span className="revision-topic">
                  {item.topic || "General"}
                </span>
                {item.difficulty && (
                  <span className="revision-difficulty">{item.difficulty}</span>
                )}
              </div>
              <div className="revision-question">{item.question_text}</div>
              {item.explanation && (
                <div className="revision-explanation">{item.explanation}</div>
              )}
              <div className="revision-meta">{item.exam_title}</div>
              <div className="revision-actions">
                {item.status !== "reviewed" && (
                  <Button
                    variant="secondary"
                    onClick={() => move(item, "reviewed")}
                  >
                    Reviewed
                  </Button>
                )}
                {item.status !== "mastered" && (
                  <Button onClick={() => move(item, "mastered")}>
                    Mastered
                  </Button>
                )}
                {item.status !== "pending" && (
                  <Button variant="ghost" onClick={() => move(item, "pending")}>
                    Back to revise
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
