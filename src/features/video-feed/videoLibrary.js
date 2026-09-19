export const VIDEO_LIBRARY = [
  {
    id: "newtons-law-of-motion",
    title: "Newton's law of motion",
    description:
      "A quick physics revision clip on forces, motion and acceleration.",
    src: "/videos/Newtonslawofmotion.mp4",
    poster: "",
    topics: [
      "physics",
      "motion",
      "forces",
      "newton",
      "newtons laws",
      "acceleration",
    ],
    skills: ["formula use", "conceptual understanding", "application"],
    level: "Core physics",
  },
  {
    id: "moon-during-day",
    title: "Why can you see the moon during the day?",
    description: "Revise moon phases, reflected light and Earth-space observation.",
    src: "/videos/Why can you see the moon during the day.mp4",
    poster: "",
    topics: [
      "physics",
      "astronomy",
      "moon",
      "space",
      "light",
      "reflection",
      "earth",
    ],
    skills: ["observation", "conceptual understanding", "explanation"],
    level: "Space science",
  },
  {
    id: "record-players",
    title: "How record players actually work",
    description: "A practical look at vibrations, sound waves and analogue audio.",
    src: "/videos/How Record Players Actually Work!.mp4",
    poster: "",
    topics: ["physics", "sound", "waves", "vibrations", "music", "technology"],
    skills: ["conceptual understanding", "systems thinking", "application"],
    level: "Applied physics",
  },
  {
    id: "faster-than-sound",
    title: "First object faster than sound",
    description: "Revise speed, sound barriers and what supersonic motion means.",
    src: "/videos/First Object Faster Than Sound!.mp4",
    poster: "",
    topics: ["physics", "sound", "speed", "supersonic", "motion", "waves"],
    skills: ["comparison", "conceptual understanding", "application"],
    level: "Motion and sound",
  },
  {
    id: "liquids-are-weird",
    title: "Liquids are weird",
    description:
      "A fast science clip for fluids, states of matter and material behaviour.",
    src: "/videos/Liquids are weird....mp4",
    poster: "",
    topics: [
      "physics",
      "chemistry",
      "liquids",
      "fluids",
      "states of matter",
      "materials",
    ],
    skills: ["observation", "conceptual understanding", "classification"],
    level: "Matter and fluids",
  },
];

function normalize(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function tokens(value) {
  return normalize(value)
    .split(/[^a-z0-9]+/i)
    .filter((token) => token.length > 2);
}

function scoreMatch(video, weakSignals) {
  const videoTerms = new Set([
    ...video.topics.flatMap(tokens),
    ...video.skills.flatMap(tokens),
    ...tokens(video.title),
    ...tokens(video.description),
  ]);

  return weakSignals.reduce((score, signal) => {
    const signalTokens = tokens(signal.label);
    const matched = signalTokens.some((token) => videoTerms.has(token));
    return score + (matched ? signal.weight : 0);
  }, 0);
}

export function rankVideosForWeaknesses(videos, weakSignals) {
  return [...videos]
    .map((video, index) => ({
      ...video,
      relevance: scoreMatch(video, weakSignals),
      originalIndex: index,
    }))
    .sort(
      (a, b) => b.relevance - a.relevance || a.originalIndex - b.originalIndex,
    );
}

export function buildWeakSignals(exams) {
  const signals = new Map();

  function add(label, weight) {
    const key = normalize(label);
    if (!key) return;
    signals.set(key, {
      label,
      weight: (signals.get(key)?.weight || 0) + weight,
    });
  }

  exams.forEach((exam) => {
    exam.analysis?.overall_weaknesses?.forEach((weakness) => add(weakness, 4));
    exam.questions?.forEach((question) => {
      const correctness = normalize(question.correctness);
      const score = Number(question.student_score);
      const max = Number(question.max_marks);
      const markRatio =
        Number.isFinite(score) && Number.isFinite(max) && max > 0
          ? score / max
          : null;
      const missed =
        ["incorrect", "partially_correct", "unanswered"].includes(
          correctness,
        ) || markRatio < 0.6;

      if (missed) {
        add(question.topic, 5);
        add(question.error_type, 3);
        add(question.difficulty, 1);
      }
    });
  });

  return [...signals.values()].sort((a, b) => b.weight - a.weight);
}
