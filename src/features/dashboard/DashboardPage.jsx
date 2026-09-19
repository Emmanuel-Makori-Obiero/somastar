import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { examApi } from "../../services/api";
import { Card, Button, EmptyState, StatPill } from "../../components/ui/ui.jsx";
import { IN_PROGRESS } from "../exam-analysis/useExamPolling";
import "./DashboardPage.css";

export default function DashboardPage() {
  const [exams, setExams] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function load() {
      try {
        const list = await examApi.list();
        if (cancelled) return;
        setExams(list);
        // Keep the list fresh while anything is still being analysed.
        if (list.some((e) => IN_PROGRESS.includes(e.status))) timer = setTimeout(load, 3000);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const completed = useMemo(() => (exams || []).filter((e) => e.status === "completed" && e.percentage_score != null), [exams]);

  const chartData = useMemo(
    () =>
      [...completed]
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .map((e) => ({
          name: e.title.length > 14 ? `${e.title.slice(0, 14)}…` : e.title,
          percentage: e.percentage_score,
        })),
    [completed]
  );

  if (error) return <p style={{ color: "var(--color-danger)" }}>{error}</p>;
  if (exams === null) return <p>Loading dashboard…</p>;

  const avg = completed.length
    ? Math.round(completed.reduce((sum, e) => sum + e.percentage_score, 0) / completed.length)
    : null;

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div>
          <h1>Your exam intelligence</h1>
          <p>Upload evidence of learning and track how you're growing.</p>
        </div>
        <Link to="/upload">
          <Button>Upload exam</Button>
        </Link>
      </div>

      <div className="dashboard-stats">
        <Card>
          <StatPill label="Exams analysed" value={completed.length} />
        </Card>
        <Card>
          <StatPill label="Average score" value={avg !== null ? `${avg}%` : "—"} />
        </Card>
        <Card>
          <StatPill label="Total exams" value={exams.length} />
        </Card>
      </div>

      {chartData.length >= 2 && (
        <Card>
          <h2>Score trend</h2>
          <div className="dashboard-chart">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Line type="monotone" dataKey="percentage" stroke="#907AF2" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      <Card>
        <h2>Recent exams</h2>
        {exams.length === 0 ? (
          <EmptyState
            title="Your exam intelligence starts here."
            description="Upload your first paper and we'll break down your performance, errors and demonstrated skills."
            action={
              <Link to="/upload">
                <Button>Upload your first exam</Button>
              </Link>
            }
          />
        ) : (
          <ul className="dashboard-exam-list">
            {exams.map((exam) => (
              <li key={exam.id}>
                <Link to={`/exams/${exam.id}`} className="dashboard-exam-row">
                  <div>
                    <div className="dashboard-exam-title">{exam.title}</div>
                    <div className="dashboard-exam-meta">
                      {exam.exam_round || "—"} · {new Date(exam.created_at).toLocaleDateString()}
                      {exam.percentage_score != null && ` · ${exam.percentage_score}%`}
                    </div>
                  </div>
                  <span className={`dashboard-exam-status status-${exam.status}`}>
                    {exam.status.replace(/_/g, " ")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
