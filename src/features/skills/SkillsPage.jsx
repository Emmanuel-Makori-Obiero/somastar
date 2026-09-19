import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { assessmentApi } from "../../services/api";
import { Card, Button, EmptyState } from "../../components/ui/ui.jsx";
import "./SkillsPage.css";

function level(score) {
  if (score >= 70) return "strong";
  if (score >= 50) return "developing";
  return "needs-work";
}

const LEVEL_LABEL = { strong: "Strong", developing: "Developing", "needs-work": "Needs work" };

export default function SkillsPage() {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    assessmentApi
      .get()
      .then((data) => setProfile(data.profile || []))
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p style={{ color: "var(--color-danger)" }}>{error}</p>;
  if (profile === null) return <p>Loading skills…</p>;

  if (profile.length === 0) {
    return (
      <EmptyState
        title="No skills mapped yet"
        description="Skills are built from the questions in your analysed exams. Upload an exam to get started."
        action={
          <Link to="/upload">
            <Button>Upload an exam</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="skills-page">
      <h1>Skills</h1>
      <p>What your exams show you can do, based on how you scored on the questions that tested each skill.</p>

      <div className="skills-list">
        {profile.map((s) => {
          const lv = level(s.average_score);
          return (
            <Card key={s.skill} className="skill-row">
              <div className="skill-row-head">
                <span className="skill-name">{s.skill}</span>
                <span className={`skill-level skill-level-${lv}`}>{LEVEL_LABEL[lv]}</span>
              </div>
              <div
                className="skill-bar"
                role="progressbar"
                aria-valuenow={Math.round(s.average_score)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${s.skill} average score`}
              >
                <div className={`skill-bar-fill skill-bar-${lv}`} style={{ width: `${Math.min(100, s.average_score)}%` }} />
              </div>
              <div className="skill-meta">
                {s.average_score}% average · {s.evidence_count} {s.evidence_count === 1 ? "question" : "questions"}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
