import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { examApi } from "../../services/api";
import { Card, Button, ErrorBanner } from "../../components/ui/ui.jsx";
import { useExamPolling, IN_PROGRESS } from "./useExamPolling";
import "./ExamPages.css";

const STAGES = [
  { status: "queued", label: "Queued" },
  { status: "extracting", label: "Reading your paper" },
  { status: "analysing_questions", label: "Analysing questions" },
  { status: "generating_skills", label: "Mapping skills" },
  { status: "aggregating", label: "Building your summary" },
];

function correctnessLabel(c) {
  if (!c) return "Unavailable";
  return c.replace(/_/g, " ");
}

function ProcessingCard({ status }) {
  const activeIndex = Math.max(0, STAGES.findIndex((s) => s.status === status));
  return (
    <div className="processing-page">
      <Card className="processing-card" role="status" aria-live="polite">
        <h2>Analysing your exam</h2>
        <p>This can take up to a minute for a full paper. You can leave this page — it keeps running.</p>
        <ul className="processing-stages">
          {STAGES.map((stage, idx) => (
            <li key={stage.status} className={idx < activeIndex ? "done" : idx === activeIndex ? "done active" : ""}>
              <span className="processing-dot" />
              {stage.label}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

export default function ExamAnalysisPage() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const { exam, error, refresh } = useExamPolling(examId);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleReanalyze() {
    setActionError("");
    setBusy(true);
    try {
      await examApi.reanalyze(examId);
      refresh();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this exam and everything derived from it? This can't be undone.")) return;
    setActionError("");
    setBusy(true);
    try {
      await examApi.remove(examId);
      navigate("/dashboard");
    } catch (err) {
      setActionError(err.message);
      setBusy(false);
    }
  }

  if (error && !exam) return <p style={{ color: "var(--color-danger)" }}>{error}</p>;
  if (!exam) return <p>Loading analysis…</p>;

  if (IN_PROGRESS.includes(exam.status)) return <ProcessingCard status={exam.status} />;

  if (exam.status === "failed") {
    return (
      <div className="exam-page">
        <h1>{exam.title}</h1>
        <Card className="failed-card">
          <h2>We couldn't analyse this exam</h2>
          <p>{exam.error_message || "Something went wrong while analysing this exam."}</p>
          <ErrorBanner message={actionError} />
          <div className="analysis-actions">
            <Button onClick={handleReanalyze} disabled={busy}>Try again</Button>
            <Button variant="secondary" onClick={handleDelete} disabled={busy}>Delete exam</Button>
          </div>
        </Card>
      </div>
    );
  }

  const { analysis, questions } = exam;

  return (
    <div className="exam-page">
      <div className="analysis-header">
        <div>
          <h1>{exam.title}</h1>
          <p>{exam.exam_round || "—"} · {new Date(exam.created_at).toLocaleDateString()}</p>
        </div>
        {analysis?.percentage_score != null && (
          <div className="analysis-score">
            <span className="analysis-score-value">{analysis.percentage_score}%</span>
            <span className="analysis-score-label">overall</span>
          </div>
        )}
      </div>

      <ErrorBanner message={actionError} />

      {analysis?.executive_summary && (
        <Card className="analysis-summary">
          <h2>Executive summary</h2>
          <p>{analysis.executive_summary}</p>
          <div className="analysis-tags">
            {analysis.overall_strengths.map((s) => (
              <span key={`s-${s}`} className="tag tag-strength">{s}</span>
            ))}
            {analysis.overall_weaknesses.map((w) => (
              <span key={`w-${w}`} className="tag tag-weakness">{w}</span>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h2>Question breakdown</h2>
        <div className="question-table">
          <div className="question-row question-row-head">
            <span>Q#</span>
            <span>Topic</span>
            <span>Marks</span>
            <span>Difficulty</span>
            <span>Correctness</span>
            <span>Error type</span>
          </div>
          {questions.map((q) => (
            <div className="question-row" key={q.id}>
              <span>{q.question_number}</span>
              <span>{q.topic || "—"}</span>
              <span>{q.student_score != null ? `${q.student_score}/${q.max_marks}` : `—/${q.max_marks}`}</span>
              <span className="capitalize">{q.difficulty || "—"}</span>
              <span className={`correctness-pill correctness-${q.correctness || "unavailable"}`}>
                {correctnessLabel(q.correctness)}
              </span>
              <span>{q.error_type ? q.error_type.replace(/_/g, " ") : "—"}</span>
            </div>
          ))}
        </div>
      </Card>

      <div className="analysis-actions">
        <Button variant="secondary" onClick={handleReanalyze} disabled={busy}>Re-analyse</Button>
        <Button variant="secondary" onClick={handleDelete} disabled={busy}>Delete exam</Button>
      </div>
    </div>
  );
}
