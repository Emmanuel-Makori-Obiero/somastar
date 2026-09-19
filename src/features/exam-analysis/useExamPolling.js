import { useCallback, useEffect, useState } from "react";
import { examApi } from "../../services/api";

export const IN_PROGRESS = ["queued", "extracting", "analysing_questions", "generating_skills", "aggregating"];

/**
 * Loads an exam and keeps polling while the backend is still analysing it, so
 * the progress the user sees is the real pipeline status (no fake timers).
 */
export function useExamPolling(examId, intervalMs = 1500) {
  const [exam, setExam] = useState(null);
  const [error, setError] = useState("");
  const [generation, setGeneration] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer;

    async function load() {
      try {
        const data = await examApi.get(examId);
        if (cancelled) return;
        setExam(data);
        setError("");
        if (IN_PROGRESS.includes(data.status)) timer = setTimeout(load, intervalMs);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [examId, intervalMs, generation]);

  const refresh = useCallback(() => setGeneration((g) => g + 1), []);
  return { exam, error, refresh };
}
