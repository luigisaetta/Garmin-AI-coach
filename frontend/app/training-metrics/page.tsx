"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-10
 * License: MIT
 */

import {
  Activity,
  BarChart3,
  Bike,
  BookOpenText,
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  Gauge,
  MessageSquareText,
  Moon,
  RefreshCcw,
  Settings2,
  Sparkles,
  Sun,
  TrendingUp,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Theme = "light" | "black";
type MetricsState = "idle" | "loading" | "ready" | "error";
type AnalysisState = "idle" | "loading" | "ready" | "error";
type RangePreset = "week" | "month" | "currentMonth" | "custom";
type SportKey = "running" | "cycling" | "swimming";
type IntensitySource = "training_load" | "intensity_minutes" | "none";

type SportMetrics = {
  sport: SportKey;
  label: string;
  activity_count: number;
  hours: number;
  total_duration_seconds: number;
  total_training_load: number | null;
  training_load_per_hour: number | null;
  weighted_average_heart_rate: number | null;
  average_aerobic_training_effect: number | null;
  average_anaerobic_training_effect: number | null;
  moderate_intensity_minutes: number;
  vigorous_intensity_minutes: number;
  intensity_score: number | null;
  intensity_source: IntensitySource;
};

type TrainingMetricsResponse = {
  begin_date: string;
  end_date: string;
  sports: SportMetrics[];
};

type TrainingMetricsAnalysisResponse = {
  begin_date: string;
  end_date: string;
  analysis: string;
  token_usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  } | null;
};

const RANGE_PRESETS: { value: RangePreset; label: string }[] = [
  { value: "week", label: "Last 7 days" },
  { value: "month", label: "Last 30 days" },
  { value: "currentMonth", label: "Current month" },
  { value: "custom", label: "Custom" },
];

const SPORT_ICONS = {
  running: Activity,
  cycling: Bike,
  swimming: Waves,
};

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date: Date, days: number) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + days);
  return nextDate;
}

function defaultRange() {
  const today = new Date();
  return {
    beginDate: isoDate(addDays(today, -6)),
    endDate: isoDate(today),
  };
}

function rangeForPreset(preset: RangePreset) {
  const today = new Date();
  if (preset === "month") {
    return {
      beginDate: isoDate(addDays(today, -29)),
      endDate: isoDate(today),
    };
  }
  if (preset === "currentMonth") {
    return {
      beginDate: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)),
      endDate: isoDate(today),
    };
  }
  return defaultRange();
}

function formatHours(hours: number) {
  return `${hours.toFixed(1)} h`;
}

function formatNumber(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
  }).format(value);
}

function formatHeartRate(value: number | null) {
  if (value === null) {
    return "-";
  }
  return `${formatNumber(value)} bpm`;
}

export default function TrainingMetricsPage() {
  const initialRange = defaultRange();
  const [theme, setTheme] = useState<Theme>("light");
  const [preset, setPreset] = useState<RangePreset>("week");
  const [beginDate, setBeginDate] = useState(initialRange.beginDate);
  const [endDate, setEndDate] = useState(initialRange.endDate);
  const [metricsState, setMetricsState] = useState<MetricsState>("idle");
  const [metrics, setMetrics] = useState<TrainingMetricsResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready to load metrics");
  const [analysisState, setAnalysisState] = useState<AnalysisState>("idle");
  const [analysis, setAnalysis] =
    useState<TrainingMetricsAnalysisResponse | null>(null);
  const [analysisMessage, setAnalysisMessage] = useState(
    "Generate a coach summary when metrics are ready",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    loadMetrics(beginDate, endDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totals = useMemo(() => {
    const sports = metrics?.sports ?? [];
    return {
      hours: sports.reduce((total, sport) => total + sport.hours, 0),
      activities: sports.reduce(
        (total, sport) => total + sport.activity_count,
        0,
      ),
      intensity: sports.reduce(
        (total, sport) => total + (sport.intensity_score ?? 0),
        0,
      ),
    };
  }, [metrics]);

  const maxHours = useMemo(
    () => Math.max(1, ...(metrics?.sports.map((sport) => sport.hours) ?? [0])),
    [metrics],
  );
  const maxIntensity = useMemo(
    () =>
      Math.max(
        1,
        ...(metrics?.sports.map((sport) => sport.intensity_score ?? 0) ?? [0]),
      ),
    [metrics],
  );

  function handlePresetChange(nextPreset: RangePreset) {
    setPreset(nextPreset);
    if (nextPreset === "custom") {
      return;
    }
    const nextRange = rangeForPreset(nextPreset);
    setBeginDate(nextRange.beginDate);
    setEndDate(nextRange.endDate);
    loadMetrics(nextRange.beginDate, nextRange.endDate);
  }

  async function loadMetrics(nextBeginDate = beginDate, nextEndDate = endDate) {
    if (nextBeginDate > nextEndDate) {
      setMetricsState("error");
      setStatusMessage("Start date must be before end date");
      return;
    }

    setMetricsState("loading");
    setStatusMessage("Loading Garmin activities");
    setAnalysisState("idle");
    setAnalysis(null);
    setAnalysisMessage("Generate a coach summary when metrics are ready");

    try {
      const params = new URLSearchParams({
        begin_date: nextBeginDate,
        end_date: nextEndDate,
      });
      const response = await fetch(`/api/training/metrics?${params}`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Training metrics API returned HTTP ${response.status}`);
      }

      const nextMetrics = (await response.json()) as TrainingMetricsResponse;
      setMetrics(nextMetrics);
      setMetricsState("ready");
      setStatusMessage("Metrics loaded");
    } catch {
      setMetricsState("error");
      setStatusMessage("Could not load training metrics");
    }
  }

  async function generateAnalysis() {
    const activeBeginDate = metrics?.begin_date ?? beginDate;
    const activeEndDate = metrics?.end_date ?? endDate;

    if (!metrics || metricsState !== "ready") {
      setAnalysisState("error");
      setAnalysisMessage("Load metrics before generating the analysis");
      return;
    }

    setAnalysisState("loading");
    setAnalysisMessage("Generating AI coach analysis");

    try {
      const response = await fetch("/api/training/metrics/analysis", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          begin_date: activeBeginDate,
          end_date: activeEndDate,
          response_language: "italian",
        }),
      });

      if (!response.ok) {
        throw new Error(
          `Training metrics analysis API returned HTTP ${response.status}`,
        );
      }

      const nextAnalysis =
        (await response.json()) as TrainingMetricsAnalysisResponse;
      setAnalysis(nextAnalysis);
      setAnalysisState("ready");
      setAnalysisMessage("AI analysis ready");
    } catch {
      setAnalysisState("error");
      setAnalysisMessage("Could not generate the AI analysis");
    }
  }

  function handleCustomSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreset("custom");
    loadMetrics(beginDate, endDate);
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Training metrics controls">
        <section className="brand">
          <span className="brandMark" aria-hidden="true">
            <Activity size={24} />
          </span>
          <span>
            <h1>Personal Training AI Coach</h1>
            <p>Training intelligence console</p>
          </span>
        </section>

        <nav className="panel navPanel" aria-label="Main navigation">
          <div className="panelTitle">
            <BarChart3 size={17} />
            <h2>Navigation</h2>
          </div>
          <Link className="navItem" href="/">
            <MessageSquareText size={16} />
            <span>Coach chat</span>
          </Link>
          <Link
            className="navItem active"
            href="/training-metrics"
            aria-current="page"
          >
            <BarChart3 size={16} />
            <span>Training metrics</span>
          </Link>
          <Link className="navItem" href="/training-trends">
            <TrendingUp size={16} />
            <span>Training trends</span>
          </Link>
          <Link className="navItem" href="/nutrition-diary">
            <BookOpenText size={16} />
            <span>Food diary</span>
          </Link>
        </nav>

        <section className="panel">
          <div className="panelTitle">
            <Gauge size={17} />
            <h2>Status</h2>
          </div>
          <div
            className={`statusLine ${
              metricsState === "error"
                ? "offline"
                : metricsState === "ready"
                  ? "online"
                  : "checking"
            }`}
          >
            {metricsState === "error" ? (
              <CircleAlert size={17} />
            ) : (
              <CheckCircle2 size={17} />
            )}
            <span>{statusMessage}</span>
          </div>
          <div className="miniGrid">
            <div className="metric teal">
              <small>Hours</small>
              <strong>{formatHours(totals.hours)}</strong>
            </div>
            <div className="metric coral">
              <small>Workouts</small>
              <strong>{totals.activities}</strong>
            </div>
            <div className="metric gold">
              <small>Intensity</small>
              <strong>{formatNumber(totals.intensity)}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <CalendarDays size={17} />
            <h2>Range</h2>
          </div>
          <div className="rangePresetGrid" role="group" aria-label="Date range">
            {RANGE_PRESETS.map((rangePreset) => (
              <button
                className={preset === rangePreset.value ? "active" : ""}
                key={rangePreset.value}
                type="button"
                onClick={() => handlePresetChange(rangePreset.value)}
              >
                {rangePreset.label}
              </button>
            ))}
          </div>
          <form className="sidebarDateForm" onSubmit={handleCustomSubmit}>
            <label>
              <span>From</span>
              <input
                type="date"
                value={beginDate}
                onChange={(event) => {
                  setPreset("custom");
                  setBeginDate(event.target.value);
                }}
              />
            </label>
            <label>
              <span>To</span>
              <input
                type="date"
                value={endDate}
                onChange={(event) => {
                  setPreset("custom");
                  setEndDate(event.target.value);
                }}
              />
            </label>
            <button
              className="sidebarAction"
              disabled={metricsState === "loading"}
              type="submit"
            >
              <RefreshCcw size={16} />
              <span>Refresh</span>
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <Settings2 size={17} />
            <h2>Settings</h2>
          </div>
          <div className="themeSwitch" role="group" aria-label="Theme">
            <button
              className={theme === "light" ? "active" : ""}
              type="button"
              onClick={() => setTheme("light")}
              title="Light theme"
            >
              <Sun size={16} />
              <span>Light</span>
            </button>
            <button
              className={theme === "black" ? "active" : ""}
              type="button"
              onClick={() => setTheme("black")}
              title="Black theme"
            >
              <Moon size={16} />
              <span>Black</span>
            </button>
          </div>
        </section>
      </aside>

      <section className="metricsShell" aria-label="Training metrics">
        <header className="topbar">
          <span>
            <h2>Training metrics</h2>
            <p>
              {metrics
                ? `${metrics.begin_date} to ${metrics.end_date}`
                : `${beginDate} to ${endDate}`}
            </p>
          </span>
          <div className="topSignal">
            <BarChart3 size={18} />
            <span>Run, bike, swim</span>
          </div>
        </header>

        <div className="metricsGrid">
          {(metrics?.sports ?? []).map((sport) => {
            const Icon = SPORT_ICONS[sport.sport];
            const hourWidth = `${Math.max(4, (sport.hours / maxHours) * 100)}%`;
            const intensityWidth = `${Math.max(
              4,
              ((sport.intensity_score ?? 0) / maxIntensity) * 100,
            )}%`;

            return (
              <article className={`sportPanel ${sport.sport}`} key={sport.sport}>
                <div className="sportPanelHeader">
                  <span className="diaryIcon" aria-hidden="true">
                    <Icon size={18} />
                  </span>
                  <span>
                    <h3>{sport.label}</h3>
                    <p>{sport.activity_count} workout(s)</p>
                  </span>
                </div>

                <div className="sportNumbers">
                  <div>
                    <small>Hours</small>
                    <strong>{formatHours(sport.hours)}</strong>
                  </div>
                  <div>
                    <small>Training load</small>
                    <strong>{formatNumber(sport.total_training_load)}</strong>
                  </div>
                  <div>
                    <small>Load / hour</small>
                    <strong>{formatNumber(sport.training_load_per_hour)}</strong>
                  </div>
                  <div>
                    <small>Weighted HR</small>
                    <strong>{formatHeartRate(sport.weighted_average_heart_rate)}</strong>
                  </div>
                  <div>
                    <small>Aerobic TE</small>
                    <strong>
                      {formatNumber(sport.average_aerobic_training_effect)}
                    </strong>
                  </div>
                  <div>
                    <small>Anaerobic TE</small>
                    <strong>
                      {formatNumber(sport.average_anaerobic_training_effect)}
                    </strong>
                  </div>
                </div>

                <div className="barGroup">
                  <span>Volume</span>
                  <div className="metricBar">
                    <i style={{ width: hourWidth }} />
                  </div>
                </div>

                <div className="barGroup">
                  <span>Intensity</span>
                  <div className="metricBar intensity">
                    <i style={{ width: intensityWidth }} />
                  </div>
                </div>

                <dl className="previewList">
                  <div>
                    <dt>Moderate minutes</dt>
                    <dd>{formatNumber(sport.moderate_intensity_minutes)}</dd>
                  </div>
                  <div>
                    <dt>Vigorous minutes</dt>
                    <dd>{formatNumber(sport.vigorous_intensity_minutes)}</dd>
                  </div>
                  <div>
                    <dt>Training load</dt>
                    <dd>{formatNumber(sport.total_training_load)}</dd>
                  </div>
                  <div>
                    <dt>Load per hour</dt>
                    <dd>{formatNumber(sport.training_load_per_hour)}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>

        <section className="analysisPanel" aria-label="AI training analysis">
          <div className="analysisHeader">
            <span>
              <Sparkles size={18} />
              <span>
                <h3>AI coach analysis</h3>
                <p>{analysisMessage}</p>
              </span>
            </span>
            <button
              className="analysisButton"
              type="button"
              disabled={metricsState !== "ready" || analysisState === "loading"}
              onClick={() => {
                void generateAnalysis();
              }}
            >
              <Sparkles size={16} />
              <span>
                {analysisState === "loading" ? "Generating" : "Generate analysis"}
              </span>
            </button>
          </div>

          {analysisState === "ready" && analysis ? (
            <div className="analysisText markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ children, ...props }) => (
                    <a {...props} rel="noreferrer" target="_blank">
                      {children}
                    </a>
                  ),
                }}
              >
                {analysis.analysis}
              </ReactMarkdown>
            </div>
          ) : (
            <div
              className={`analysisPlaceholder ${
                analysisState === "error" ? "error" : ""
              }`}
            >
              <p>
                {analysisState === "error"
                  ? analysisMessage
                  : "The analysis uses only the aggregate metrics shown above and is generated on demand."}
              </p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
