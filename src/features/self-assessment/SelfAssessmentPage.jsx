import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from "recharts";
import { assessmentApi } from "../../services/api";
import { Card, EmptyState, Button } from "../../components/ui/ui.jsx";
import "./SelfAssessmentPage.css";

export default function SelfAssessmentPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState([]);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    assessmentApi
      .get()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  async function sendMessage(e) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = { role: "user", content: chatInput };
    setChatLog((log) => [...log, userMsg]);
    setChatInput("");
    setSending(true);
    try {
      const reply = await assessmentApi.chat(userMsg.content);
      setChatLog((log) => [...log, reply]);
    } catch (err) {
      setChatLog((log) => [...log, { role: "assistant", content: `Error: ${err.message}` }]);
    } finally {
      setSending(false);
    }
  }

  if (error) return <p style={{ color: "var(--color-danger)" }}>{error}</p>;
  if (!data) return <p>Loading self assessment…</p>;

  if (data.exams_analysed === 0) {
    return (
      <EmptyState
        title="Your skill profile will appear after your first analysed exam."
        description="Upload an exam to unlock performance trends, strengths, weaknesses and career suggestions."
      />
    );
  }

  const trendData = data.trend.map((t) => ({
    name: t.exam_title.length > 14 ? t.exam_title.slice(0, 14) + "…" : t.exam_title,
    percentage: t.percentage,
  }));

  const skillData = [...data.strengths, ...data.weaknesses].map((s) => ({
    name: s.skill,
    score: s.average_score,
  }));

  return (
    <div className="assessment-page">
      <h1>Self assessment</h1>
      <p>An aggregate view of your strengths, weaknesses and growth over time.</p>

      <div className="assessment-grid">
        <div className="assessment-main">
          <Card>
            <h2>Performance trend</h2>
            {trendData.length < 2 ? (
              <p className="assessment-note">We need at least two comparable exams to show a performance trend.</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="percentage" stroke="#907AF2" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card>
            <h2>Skill profile</h2>
            {skillData.length === 0 ? (
              <p className="assessment-note">Analyse more exams to build a skill profile.</p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(180, skillData.length * 40)}>
                <BarChart data={skillData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={140} />
                  <Tooltip />
                  <Bar dataKey="score" fill="#907AF2" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card>
            <h2>Career suggestions</h2>
            <div className="career-tags">
              {data.career_suggestions.map((c) => (
                <span key={c} className="career-tag">{c}</span>
              ))}
            </div>
          </Card>
        </div>

        <div className="assessment-side">
          <Card>
            <h2>Overview</h2>
            <div className="assessment-overview">
              <div>
                <div className="overview-value">{data.overall_average ?? "—"}%</div>
                <div className="overview-label">Overall average</div>
              </div>
              <div>
                <div className="overview-value">{data.exams_analysed}</div>
                <div className="overview-label">Exams analysed</div>
              </div>
            </div>
          </Card>

          <Card className="assistant-card">
            <h2>Ask your assistant</h2>
            <div className="assistant-log">
              {chatLog.length === 0 && (
                <p className="assessment-note">Ask about your trends, weak topics, or what to revise next.</p>
              )}
              {chatLog.map((m, i) => (
                <div key={i} className={`assistant-msg assistant-msg-${m.role}`}>
                  {m.content}
                </div>
              ))}
            </div>
            <form onSubmit={sendMessage} className="assistant-form">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="What should I revise next?"
              />
              <Button type="submit" disabled={sending}>
                {sending ? "…" : "Send"}
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </div>
  );
}
