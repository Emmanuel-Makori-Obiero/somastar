import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { examApi } from "../../services/api";
import { Card, Button, ErrorBanner } from "../../components/ui/ui.jsx";
import "./ExamPages.css";

const MAX_MB = 10;

export default function UploadPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [examRound, setExamRound] = useState("");
  const [totalMarks, setTotalMarks] = useState("");
  const [file, setFile] = useState(null);
  const [structured, setStructured] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function handleFile(e) {
    const picked = e.target.files?.[0] || null;
    if (picked && picked.size > MAX_MB * 1024 * 1024) {
      setError(`That file is larger than ${MAX_MB} MB. Try a smaller scan or a compressed PDF.`);
      e.target.value = "";
      setFile(null);
      return;
    }
    setError("");
    setFile(picked);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!file && !structured.trim()) {
      setError("Add the exam paper or paste a question breakdown so there's something to analyse.");
      return;
    }
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("subject_name", subject);
      if (examRound) formData.append("exam_round", examRound);
      if (totalMarks) formData.append("total_marks", totalMarks);
      if (structured.trim()) formData.append("extracted_text", structured);
      if (file) formData.append("file", file);

      // The API answers immediately; the analysis page shows the real progress.
      const exam = await examApi.upload(formData);
      navigate(`/exams/${exam.id}`);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="exam-page">
      <h1>Upload an exam</h1>
      <p>Give us the paper and, where possible, marks — we'll break down performance and skills.</p>

      <Card className="upload-card">
        <ErrorBanner message={error} />
        <form onSubmit={handleSubmit} className="upload-form">
          <label>
            Exam title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} placeholder="Mid-Term Physics" />
          </label>
          <div className="upload-row">
            <label>
              Subject
              <input value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={100} placeholder="Physics" />
            </label>
            <label>
              Exam round
              <input value={examRound} onChange={(e) => setExamRound(e.target.value)} maxLength={100} placeholder="Term 1" />
            </label>
          </div>
          <label>
            Total marks <span className="upload-optional">(optional)</span>
            <input type="number" min="1" step="any" value={totalMarks} onChange={(e) => setTotalMarks(e.target.value)} placeholder="40" />
          </label>
          <label>
            Exam paper <span className="upload-optional">(PDF, PNG or JPG, up to {MAX_MB} MB)</span>
            <input type="file" onChange={handleFile} accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" />
          </label>
          <label>
            Question breakdown <span className="upload-optional">(optional — improves accuracy)</span>
            <textarea
              rows={4}
              placeholder={"Q1 | Topic | max_marks | your_score\nQ2 | Topic | max_marks | your_score"}
              value={structured}
              onChange={(e) => setStructured(e.target.value)}
            />
          </label>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Uploading…" : "Analyse exam"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
