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
  CheckCircle2,
  CircleAlert,
  Gauge,
  MessageSquareText,
  Moon,
  RefreshCcw,
  Settings2,
  Sun,
  TrendingUp,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";
type TrendsState = "idle" | "loading" | "ready" | "error";
type SportKey = "running" | "cycling" | "swimming";
type WeekPreset = 8 | 12 | 16;

type TrendSport = {
  sport: SportKey;
  label: string;
  hours: number;
  training_load: number;
  activity_count: number;
};

type TrendWeek = {
  week_start: string;
  week_end: string;
  iso_year: number;
  iso_week: number;
  label: string;
  total_hours: number;
  total_training_load: number;
  activity_count: number;
  sports: TrendSport[];
  rolling_4_week_average_load: number | null;
  previous_week_delta_percent: number | null;
  acute_chronic_load_ratio: number | null;
};

type TrainingTrendsResponse = {
  begin_date: string;
  end_date: string;
  weeks_requested: number;
  weeks: TrendWeek[];
};

const WEEK_PRESETS: WeekPreset[] = [8, 12, 16];

const SPORT_ICONS = {
  running: Activity,
  cycling: Bike,
  swimming: Waves,
};

function formatNumber(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
  }).format(value);
}

function formatRatio(value: number | null) {
  if (value === null) {
    return "-";
  }
  return value.toFixed(2);
}

function formatDelta(value: number | null) {
  if (value === null) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}%`;
}

function formatHours(value: number) {
  return `${value.toFixed(1)} h`;
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function sportLoad(week: TrendWeek, sport: SportKey) {
  return (
    week.sports.find((sportTrend) => sportTrend.sport === sport)?.training_load ?? 0
  );
}

export default function TrainingTrendsPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const [weeks, setWeeks] = useState<WeekPreset>(12);
  const [trendsState, setTrendsState] = useState<TrendsState>("idle");
  const [trends, setTrends] = useState<TrainingTrendsResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready to load trends");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    loadTrends(weeks);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentWeek = trends?.weeks.at(-1) ?? null;
  const previousWeek =
    trends && trends.weeks.length > 1 ? trends.weeks.at(-2) ?? null : null;
  const maxLoad = useMemo(
    () =>
      Math.max(
        1,
        ...(trends?.weeks.map((week) => week.total_training_load) ?? [0]),
      ),
    [trends],
  );
  const totals = useMemo(() => {
    const trendWeeks = trends?.weeks ?? [];
    return {
      load: trendWeeks.reduce((total, week) => total + week.total_training_load, 0),
      hours: trendWeeks.reduce((total, week) => total + week.total_hours, 0),
      workouts: trendWeeks.reduce((total, week) => total + week.activity_count, 0),
    };
  }, [trends]);

  async function loadTrends(nextWeeks = weeks) {
    setTrendsState("loading");
    setStatusMessage("Loading weekly trend data");

    try {
      const params = new URLSearchParams({ weeks: String(nextWeeks) });
      const response = await fetch(`/api/training/trends?${params}`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Training trends API returned HTTP ${response.status}`);
      }

      const nextTrends = (await response.json()) as TrainingTrendsResponse;
      setTrends(nextTrends);
      setTrendsState("ready");
      setStatusMessage("Trends loaded");
    } catch {
      setTrendsState("error");
      setStatusMessage("Could not load training trends");
    }
  }

  function handleWeeksChange(nextWeeks: WeekPreset) {
    setWeeks(nextWeeks);
    loadTrends(nextWeeks);
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Training trends controls">
        <section className="brand">
          <span className="brandMark" aria-hidden="true">
            <TrendingUp size={24} />
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
          <Link className="navItem" href="/training-metrics">
            <BarChart3 size={16} />
            <span>Training metrics</span>
          </Link>
          <Link
            className="navItem active"
            href="/training-trends"
            aria-current="page"
          >
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
              trendsState === "error"
                ? "offline"
                : trendsState === "ready"
                  ? "online"
                  : "checking"
            }`}
          >
            {trendsState === "error" ? (
              <CircleAlert size={17} />
            ) : (
              <CheckCircle2 size={17} />
            )}
            <span>{statusMessage}</span>
          </div>
          <div className="miniGrid">
            <div className="metric teal">
              <small>Total load</small>
              <strong>{formatNumber(totals.load)}</strong>
            </div>
            <div className="metric coral">
              <small>Hours</small>
              <strong>{formatHours(totals.hours)}</strong>
            </div>
            <div className="metric gold">
              <small>Workouts</small>
              <strong>{totals.workouts}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <TrendingUp size={17} />
            <h2>Window</h2>
          </div>
          <div className="rangePresetGrid" role="group" aria-label="Trend weeks">
            {WEEK_PRESETS.map((weekPreset) => (
              <button
                className={weeks === weekPreset ? "active" : ""}
                key={weekPreset}
                type="button"
                onClick={() => handleWeeksChange(weekPreset)}
              >
                {weekPreset} weeks
              </button>
            ))}
          </div>
          <button
            className="sidebarAction"
            disabled={trendsState === "loading"}
            type="button"
            onClick={() => loadTrends(weeks)}
          >
            <RefreshCcw size={16} />
            <span>Refresh</span>
          </button>
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

      <section className="metricsShell" aria-label="Training trends">
        <header className="topbar">
          <span>
            <h2>Training trends</h2>
            <p>
              {trends
                ? `${trends.begin_date} to ${trends.end_date}`
                : `${weeks} recent ISO weeks`}
            </p>
          </span>
          <div className="topSignal">
            <TrendingUp size={18} />
            <span>Weekly load trend</span>
          </div>
        </header>

        <section className="trendSummaryGrid" aria-label="Trend summary">
          <article className="trendSummaryCard">
            <small>Current week load</small>
            <strong>{formatNumber(currentWeek?.total_training_load ?? null)}</strong>
            <span>{currentWeek?.label ?? "-"}</span>
          </article>
          <article className="trendSummaryCard">
            <small>Previous week delta</small>
            <strong>{formatDelta(currentWeek?.previous_week_delta_percent ?? null)}</strong>
            <span>{previousWeek?.label ?? "No baseline"}</span>
          </article>
          <article className="trendSummaryCard">
            <small>4-week average</small>
            <strong>
              {formatNumber(currentWeek?.rolling_4_week_average_load ?? null)}
            </strong>
            <span>Rolling load</span>
          </article>
          <article className="trendSummaryCard">
            <small>Load ratio</small>
            <strong>
              {formatRatio(currentWeek?.acute_chronic_load_ratio ?? null)}
            </strong>
            <span>Current vs prior 4w</span>
          </article>
        </section>

        <section className="trendChartPanel" aria-label="Weekly training load chart">
          <div className="trendChartHeader">
            <span>
              <h3>Weekly training load</h3>
              <p>Stacked by run, bike, swim with 4-week average context.</p>
            </span>
            <div className="trendLegend">
              <span className="running">Run</span>
              <span className="cycling">Bike</span>
              <span className="swimming">Swim</span>
            </div>
          </div>

          <div className="trendBars">
            {(trends?.weeks ?? []).map((week) => {
              const loadHeight = `${Math.max(
                3,
                (week.total_training_load / maxLoad) * 100,
              )}%`;
              const averageHeight = `${
                ((week.rolling_4_week_average_load ?? 0) / maxLoad) * 100
              }%`;
              const runningPercent =
                week.total_training_load > 0
                  ? (sportLoad(week, "running") / week.total_training_load) * 100
                  : 0;
              const cyclingPercent =
                week.total_training_load > 0
                  ? (sportLoad(week, "cycling") / week.total_training_load) * 100
                  : 0;
              const swimmingPercent =
                week.total_training_load > 0
                  ? (sportLoad(week, "swimming") / week.total_training_load) * 100
                  : 0;

              return (
                <article className="trendBarColumn" key={week.week_start}>
                  <div className="trendBarFrame">
                    <i
                      className="trendAverageMarker"
                      style={{ bottom: averageHeight }}
                    />
                    <div className="trendStack" style={{ height: loadHeight }}>
                      <span
                        className="running"
                        style={{ height: `${runningPercent}%` }}
                      />
                      <span
                        className="cycling"
                        style={{ height: `${cyclingPercent}%` }}
                      />
                      <span
                        className="swimming"
                        style={{ height: `${swimmingPercent}%` }}
                      />
                    </div>
                  </div>
                  <strong>{formatNumber(week.total_training_load)}</strong>
                  <small>{week.label.replace(/^\d{4}-/, "")}</small>
                </article>
              );
            })}
          </div>
        </section>

        <section className="trendTablePanel" aria-label="Weekly trend values">
          <div className="trendChartHeader">
            <span>
              <h3>Weekly values</h3>
              <p>Exact load, hours, delta, and load ratio by ISO week.</p>
            </span>
          </div>
          <div className="trendTableWrap">
            <table className="trendTable">
              <thead>
                <tr>
                  <th>Week</th>
                  <th>Dates</th>
                  <th>Load</th>
                  <th>4w avg</th>
                  <th>Delta</th>
                  <th>Ratio</th>
                  <th>Hours</th>
                  <th>Run</th>
                  <th>Bike</th>
                  <th>Swim</th>
                </tr>
              </thead>
              <tbody>
                {(trends?.weeks ?? []).map((week) => (
                  <tr key={week.week_start}>
                    <td>{week.label}</td>
                    <td>
                      {shortDate(week.week_start)} - {shortDate(week.week_end)}
                    </td>
                    <td>{formatNumber(week.total_training_load)}</td>
                    <td>{formatNumber(week.rolling_4_week_average_load)}</td>
                    <td>{formatDelta(week.previous_week_delta_percent)}</td>
                    <td>{formatRatio(week.acute_chronic_load_ratio)}</td>
                    <td>{formatHours(week.total_hours)}</td>
                    {(["running", "cycling", "swimming"] as SportKey[]).map(
                      (sport) => {
                        const Icon = SPORT_ICONS[sport];
                        return (
                          <td key={sport}>
                            <span className={`sportCell ${sport}`}>
                              <Icon size={14} />
                              {formatNumber(sportLoad(week, sport))}
                            </span>
                          </td>
                        );
                      },
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}
