import { useEffect, useMemo, useRef, useState } from "react";
import { examApi } from "../../services/api";
import { Button, ErrorBanner } from "../../components/ui/ui.jsx";
import { buildWeakSignals, rankVideosForWeaknesses, VIDEO_LIBRARY } from "./videoLibrary";
import "./VideoFeedPage.css";

const MAX_EXAMS_TO_ANALYSE = 8;

export default function VideoFeedPage() {
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const videoRefs = useRef(new Map());

  useEffect(() => {
    let cancelled = false;

    async function loadWeaknesses() {
      setLoading(true);
      setError("");
      try {
        const list = await examApi.list({ limit: MAX_EXAMS_TO_ANALYSE });
        const completed = list.filter((exam) => exam.status === "completed").slice(0, MAX_EXAMS_TO_ANALYSE);
        const fullExams = await Promise.all(completed.map((exam) => examApi.get(exam.id)));
        if (!cancelled) setExams(fullExams);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadWeaknesses();
    return () => {
      cancelled = true;
    };
  }, []);

  const weakSignals = useMemo(() => buildWeakSignals(exams), [exams]);
  const rankedVideos = useMemo(
    () => rankVideosForWeaknesses(VIDEO_LIBRARY, weakSignals),
    [weakSignals],
  );
  const topWeaknesses = weakSignals.slice(0, 5);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const video = entry.target.querySelector("video");
          if (!video) return;
          if (entry.isIntersecting) {
            videoRefs.current.forEach((otherVideo) => {
              if (otherVideo !== video) otherVideo.pause();
            });
            video.play().catch(() => {
              // Browsers may block autoplay until the learner interacts.
            });
          } else {
            video.pause();
          }
        });
      },
      { threshold: 0.72 },
    );

    const cards = document.querySelectorAll(".video-feed-card");
    cards.forEach((card) => observer.observe(card));
    return () => observer.disconnect();
  }, [rankedVideos]);

  function setVideoRef(id, node) {
    if (node) videoRefs.current.set(id, node);
    else videoRefs.current.delete(id);
  }

  return (
    <div className="video-feed-page">
      <header className="video-feed-header">
        <div>
          <p className="video-feed-kicker">Personal revision feed</p>
          <h1>Revise by watching</h1>
          <p>
            Short lessons are ranked from your weak topics first, then fall back
            to core study videos while SomaStar learns more about you.
          </p>
        </div>
        <Button variant="secondary" onClick={() => window.location.reload()}>
          Refresh feed
        </Button>
      </header>

      <ErrorBanner message={error} />

      <section className="video-feed-insights" aria-label="Feed ranking summary">
        {loading ? (
          <span>Reading your latest exam analysis...</span>
        ) : topWeaknesses.length ? (
          <>
            <span>Prioritising</span>
            {topWeaknesses.map((signal) => (
              <strong key={signal.label}>{signal.label}</strong>
            ))}
          </>
        ) : (
          <span>No weak topics yet. Upload or analyse an exam to personalise this feed.</span>
        )}
      </section>

      <div className="video-feed-rail" aria-label="Revision video feed">
        {rankedVideos.map((video, index) => (
          <article className="video-feed-card" key={video.id}>
            <video
              ref={(node) => setVideoRef(video.id, node)}
              src={video.src}
              poster={video.poster}
              controls
              muted
              loop
              playsInline
              preload="metadata"
            />
            <div className="video-feed-overlay">
              <div>
                <span className="video-feed-rank">
                  #{index + 1} · {video.level}
                </span>
                <h2>{video.title}</h2>
                <p>{video.description}</p>
                <div className="video-feed-tags">
                  {video.topics.slice(0, 3).map((topic) => (
                    <span key={topic}>{topic}</span>
                  ))}
                </div>
              </div>
              {video.relevance > 0 && (
                <span className="video-feed-match">Matched to weak point</span>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
