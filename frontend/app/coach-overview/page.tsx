"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-15
 * License: MIT
 */

import {
  Activity,
  BarChart3,
  Bike,
  BookOpenText,
  CheckCircle2,
  CircleAlert,
  FileText,
  Flag,
  Gauge,
  LayoutDashboard,
  MessageSquareText,
  Moon,
  RefreshCcw,
  ShieldAlert,
  Sun,
  TrendingUp,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";
type OverviewState = "idle" | "loading" | "ready" | "error";
type SportKey = "running" | "cycling" | "swimming";
type IntensitySource = "training_load" | "intensity_minutes" | "none";

type SportMetrics = {
  sport: SportKey;
  label: string;
  activity_count: number;
  hours: number;
  total_training_load: number | null;
  intensity_score: number | null;
  intensity_source: IntensitySource;
};

type TrainingMetricsResponse = {
  begin_date: string;
  end_date: string;
  sports: SportMetrics[];
};

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

type WeekSignalContext = {
  isInProgress: boolean;
  elapsedDays: number;
  projectedTrainingLoad: number | null;
  comparisonDeltaPercent: number | null;
  comparisonRatio: number | null;
};

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

function formatNumber(value: number | null) {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
  }).format(value);
}

function formatHours(value: number) {
  return `${value.toFixed(1)} h`;
}

function formatDelta(value: number | null) {
  if (value === null) {
    return "No baseline yet";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value)}%`;
}

function sportLoad(week: TrendWeek, sport: SportKey) {
  return (
    week.sports.find((sportTrend) => sportTrend.sport === sport)?.training_load ?? 0
  );
}

function parseIsoDate(value: string) {
  return new Date(`${value}T12:00:00`);
}

function buildWeekSignalContext(
  currentWeek: TrendWeek | null,
  previousWeeks: TrendWeek[],
  today = new Date(),
): WeekSignalContext {
  if (!currentWeek) {
    return {
      isInProgress: false,
      elapsedDays: 7,
      projectedTrainingLoad: null,
      comparisonDeltaPercent: null,
      comparisonRatio: null,
    };
  }

  const weekStart = parseIsoDate(currentWeek.week_start);
  const weekEnd = parseIsoDate(currentWeek.week_end);
  const currentDay = parseIsoDate(isoDate(today));
  const isInProgress = currentDay >= weekStart && currentDay < weekEnd;
  const elapsedDays = isInProgress
    ? Math.min(
        7,
        Math.max(
          1,
          Math.floor(
            (currentDay.getTime() - weekStart.getTime()) / 86_400_000,
          ) + 1,
        ),
      )
    : 7;
  const projectedTrainingLoad = isInProgress
    ? (currentWeek.total_training_load / elapsedDays) * 7
    : currentWeek.total_training_load;
  const previousWeek = previousWeeks.at(-1) ?? null;
  const previousLoad = previousWeek?.total_training_load ?? null;
  const recentCompletedLoads = previousWeeks
    .slice(-4)
    .map((week) => week.total_training_load)
    .filter((load) => load > 0);
  const recentCompletedAverage =
    recentCompletedLoads.length > 0
      ? recentCompletedLoads.reduce((total, load) => total + load, 0) /
        recentCompletedLoads.length
      : null;

  return {
    isInProgress,
    elapsedDays,
    projectedTrainingLoad,
    comparisonDeltaPercent:
      previousLoad !== null && previousLoad > 0
        ? ((projectedTrainingLoad - previousLoad) / previousLoad) * 100
        : null,
    comparisonRatio:
      recentCompletedAverage !== null && recentCompletedAverage > 0
        ? projectedTrainingLoad / recentCompletedAverage
        : null,
  };
}

function buildLoadSignal(context: WeekSignalContext) {
  const delta = context.comparisonDeltaPercent;
  const ratio = context.comparisonRatio;
  const prefix = context.isInProgress ? "Projected week load" : "Current load";

  if (ratio !== null && ratio !== undefined && ratio >= 1.4) {
    return {
      label: "High strain",
      detail: `${prefix} is high versus recent baseline. Keep the next hard session honest.`,
      tone: "caution",
    };
  }

  if (delta !== null && delta !== undefined && delta > 25) {
    return {
      label: "Load jump",
      detail: `${prefix} is rising quickly. A lighter day would make the trend easier to absorb.`,
      tone: "caution",
    };
  }

  if (delta !== null && delta !== undefined && delta < -20) {
    return {
      label: context.isInProgress ? "Tracking lower" : "Reduced load",
      detail: context.isInProgress
        ? "The week is still in progress; projected load is below last week if the current rhythm continues."
        : "Training load is down this week. Useful if recovery was the intention.",
      tone: "steady",
    };
  }

  return {
    label: context.isInProgress ? "Week in progress" : "Steady build",
    detail: context.isInProgress
      ? `Using ${context.elapsedDays} days of data, projected load looks controlled. Keep recovery aligned with the next quality session.`
      : "Recent load looks controlled. Keep recovery aligned with the next quality session.",
    tone: "good",
  };
}

function buildRecoverySignal(context: WeekSignalContext) {
  const ratio = context.comparisonRatio;
  const delta = context.comparisonDeltaPercent;

  if (
    (ratio !== null && ratio !== undefined && ratio >= 1.4) ||
    (delta !== null && delta !== undefined && delta > 30)
  ) {
    return {
      label: "Prioritize recovery",
      detail: "Avoid stacking intensity until sleep, legs, and motivation all feel normal.",
      tone: "caution",
    };
  }

  if (ratio !== null && ratio !== undefined && ratio < 0.8) {
    return {
      label: context.isInProgress ? "Still unfolding" : "Room to build",
      detail: context.isInProgress
        ? "The week is not complete yet, so low load is not automatically a recovery signal."
        : "Load is below the recent baseline. Add volume gradually if you feel fresh.",
      tone: "steady",
    };
  }

  return {
    label: "Normal caution",
    detail: "No obvious overload signal from the aggregate data. Still listen to fatigue.",
    tone: "good",
  };
}

export default function CoachOverviewPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const [overviewState, setOverviewState] = useState<OverviewState>("idle");
  const [statusMessage, setStatusMessage] = useState("Ready to load overview");
  const [metrics, setMetrics] = useState<TrainingMetricsResponse | null>(null);
  const [trends, setTrends] = useState<TrainingTrendsResponse | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    loadOverview();
  }, []);

  const currentWeek = trends?.weeks.at(-1) ?? null;
  const recentWeeks = useMemo(() => trends?.weeks.slice(-8) ?? [], [trends]);
  const maxWeeklyLoad = useMemo(
    () => Math.max(1, ...recentWeeks.map((week) => week.total_training_load)),
    [recentWeeks],
  );
  const totals = useMemo(() => {
    const sports = metrics?.sports ?? [];
    return {
      hours: sports.reduce((total, sport) => total + sport.hours, 0),
      activities: sports.reduce(
        (total, sport) => total + sport.activity_count,
        0,
      ),
      load: sports.reduce(
        (total, sport) => total + (sport.total_training_load ?? 0),
        0,
      ),
    };
  }, [metrics]);
  const topSport = useMemo(() => {
    const sports = [...(metrics?.sports ?? [])].sort((a, b) => b.hours - a.hours);
    return sports[0] ?? null;
  }, [metrics]);
  const previousWeeks = useMemo(() => trends?.weeks.slice(0, -1) ?? [], [trends]);
  const weekSignalContext = useMemo(
    () => buildWeekSignalContext(currentWeek, previousWeeks),
    [currentWeek, previousWeeks],
  );
  const loadSignal = buildLoadSignal(weekSignalContext);
  const recoverySignal = buildRecoverySignal(weekSignalContext);
  const weekDeltaLabel = weekSignalContext.isInProgress
    ? `Projected ${formatDelta(weekSignalContext.comparisonDeltaPercent)}`
    : formatDelta(weekSignalContext.comparisonDeltaPercent);

  async function loadOverview() {
    const endDate = new Date();
    const beginDate = addDays(endDate, -29);

    setOverviewState("loading");
    setStatusMessage("Loading Garmin overview");

    try {
      const metricsParams = new URLSearchParams({
        begin_date: isoDate(beginDate),
        end_date: isoDate(endDate),
      });
      const trendsParams = new URLSearchParams({ weeks: "12" });

      const [metricsResponse, trendsResponse] = await Promise.all([
        fetch(`/api/training/metrics?${metricsParams}`, { cache: "no-store" }),
        fetch(`/api/training/trends?${trendsParams}`, { cache: "no-store" }),
      ]);

      if (!metricsResponse.ok || !trendsResponse.ok) {
        throw new Error("Coach overview API returned an error");
      }

      setMetrics((await metricsResponse.json()) as TrainingMetricsResponse);
      setTrends((await trendsResponse.json()) as TrainingTrendsResponse);
      setOverviewState("ready");
      setStatusMessage("Overview ready");
    } catch {
      setOverviewState("error");
      setStatusMessage("Could not load coach overview");
    }
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Coach overview controls">
        <section className="brand">
          <span className="brandMark" aria-hidden="true">
            <LayoutDashboard size={24} />
          </span>
          <span>
            <h1>Personal Training AI Coach</h1>
            <p>Training intelligence console</p>
          </span>
        </section>

        <nav className="panel navPanel" aria-label="Main navigation">
          <div className="panelTitle">
            <LayoutDashboard size={17} />
            <h2>Navigation</h2>
          </div>
          <Link
            className="navItem active"
            href="/coach-overview"
            aria-current="page"
          >
            <LayoutDashboard size={16} />
            <span>Coach overview</span>
          </Link>
          <Link className="navItem" href="/">
            <MessageSquareText size={16} />
            <span>Coach chat</span>
          </Link>
          <Link className="navItem" href="/training-metrics">
            <BarChart3 size={16} />
            <span>Training metrics</span>
          </Link>
          <Link className="navItem" href="/training-trends">
            <TrendingUp size={16} />
            <span>Training trends</span>
          </Link>
          <Link className="navItem" href="/goals">
            <Flag size={16} />
            <span>Goals & races</span>
          </Link>
          <Link className="navItem" href="/nutrition-diary">
            <BookOpenText size={16} />
            <span>Food diary</span>
          </Link>
          <Link className="navItem" href="/training-reports">
            <FileText size={16} />
            <span>Training reports</span>
          </Link>
        </nav>

        <section className="panel">
          <div className="panelTitle">
            <Gauge size={17} />
            <h2>Status</h2>
          </div>
          <div
            className={`statusLine ${
              overviewState === "error"
                ? "offline"
                : overviewState === "ready"
                  ? "online"
                  : "checking"
            }`}
          >
            {overviewState === "error" ? (
              <CircleAlert size={17} />
            ) : (
              <CheckCircle2 size={17} />
            )}
            <span>{statusMessage}</span>
          </div>
          <button
            className="sidebarAction"
            disabled={overviewState === "loading"}
            type="button"
            onClick={loadOverview}
          >
            <RefreshCcw size={16} />
            Refresh overview
          </button>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <Sun size={17} />
            <h2>Theme</h2>
          </div>
          <div className="themeSwitch" role="group" aria-label="Theme switcher">
            <button
              className={theme === "light" ? "active" : ""}
              type="button"
              onClick={() => setTheme("light")}
            >
              <Sun size={15} />
              Light
            </button>
            <button
              className={theme === "black" ? "active" : ""}
              type="button"
              onClick={() => setTheme("black")}
            >
              <Moon size={15} />
              Black
            </button>
          </div>
        </section>
      </aside>

      <section className="overviewShell" aria-label="Coach overview dashboard">
        <header className="topbar">
          <span>
            <h2>Coach overview</h2>
            <p>
              Simple read on recent volume, load trend, sport mix, and recovery
              caution. Goal adherence is intentionally not shown yet.
            </p>
          </span>
          <div className="topSignal">
            <ShieldAlert size={17} />
            <span>{recoverySignal.label}</span>
          </div>
        </header>

        <section className="overviewHero" aria-label="Training status summary">
          <div className={`overviewReadiness ${loadSignal.tone}`}>
            <small>Training status</small>
            <strong>{loadSignal.label}</strong>
            <p>{loadSignal.detail}</p>
          </div>
          <div className="overviewHeroStats">
            <article>
              <small>Last 30 days</small>
              <strong>{formatHours(totals.hours)}</strong>
              <span>{totals.activities} activities</span>
            </article>
            <article>
              <small>
                {weekSignalContext.isInProgress
                  ? "Week-to-date load"
                  : "Current week load"}
              </small>
              <strong>{formatNumber(currentWeek?.total_training_load ?? null)}</strong>
              <span>{weekDeltaLabel}</span>
            </article>
            <article>
              <small>Main focus</small>
              <strong>{topSport?.label ?? "-"}</strong>
              <span>{topSport ? formatHours(topSport.hours) : "No data yet"}</span>
            </article>
          </div>
        </section>

        <section className="overviewGrid">
          <article className="overviewPanel">
            <div className="trendChartHeader">
              <span>
                <h3>Weekly load</h3>
                <p>Last eight weeks, stacked by sport.</p>
              </span>
              <div className="trendLegend">
                <span className="running">Run</span>
                <span className="cycling">Bike</span>
                <span className="swimming">Swim</span>
              </div>
            </div>
            <div className="overviewBars">
              {recentWeeks.map((week) => {
                const loadHeight = `${Math.max(
                  3,
                  (week.total_training_load / maxWeeklyLoad) * 100,
                )}%`;
                const running = sportLoad(week, "running");
                const cycling = sportLoad(week, "cycling");
                const swimming = sportLoad(week, "swimming");
                const total = Math.max(1, running + cycling + swimming);

                return (
                  <article className="trendBarColumn" key={week.week_start}>
                    <div className="trendBarFrame compact">
                      <div className="trendStack" style={{ height: loadHeight }}>
                        <span
                          className="running"
                          style={{ height: `${(running / total) * 100}%` }}
                        />
                        <span
                          className="cycling"
                          style={{ height: `${(cycling / total) * 100}%` }}
                        />
                        <span
                          className="swimming"
                          style={{ height: `${(swimming / total) * 100}%` }}
                        />
                      </div>
                    </div>
                    <strong>{week.label}</strong>
                    <small>{formatNumber(week.total_training_load)}</small>
                  </article>
                );
              })}
            </div>
          </article>

          <article className="overviewPanel">
            <div className="trendChartHeader">
              <span>
                <h3>What to watch</h3>
                <p>Plain-language signals from aggregate training data.</p>
              </span>
            </div>
            <div className="signalList">
              <div className={`signalCard ${loadSignal.tone}`}>
                <TrendingUp size={18} />
                <span>
                  <strong>{loadSignal.label}</strong>
                  <small>{loadSignal.detail}</small>
                </span>
              </div>
              <div className={`signalCard ${recoverySignal.tone}`}>
                <ShieldAlert size={18} />
                <span>
                  <strong>{recoverySignal.label}</strong>
                  <small>{recoverySignal.detail}</small>
                </span>
              </div>
              <div className="signalCard steady">
                <Gauge size={18} />
                <span>
                  <strong>
                    {weekSignalContext.isInProgress
                      ? "Projected AC ratio"
                      : "AC ratio"}
                  </strong>
                  <small>
                    {weekSignalContext.comparisonRatio === null ||
                    weekSignalContext.comparisonRatio === undefined
                      ? "Not enough baseline data yet"
                      : formatNumber(weekSignalContext.comparisonRatio)}
                  </small>
                </span>
              </div>
            </div>
          </article>
        </section>

        <section className="sportMixGrid" aria-label="Sport mix">
          {(metrics?.sports ?? []).map((sport) => {
            const Icon = SPORT_ICONS[sport.sport];
            const share =
              totals.hours > 0 ? Math.round((sport.hours / totals.hours) * 100) : 0;

            return (
              <article className={`sportPanel ${sport.sport}`} key={sport.sport}>
                <div className="sportPanelHeader">
                  <span className="diaryIcon">
                    <Icon size={19} />
                  </span>
                  <span>
                    <h3>{sport.label}</h3>
                    <p>{share}% of recent training time</p>
                  </span>
                </div>
                <div className="sportNumbers">
                  <div>
                    <small>Hours</small>
                    <strong>{formatHours(sport.hours)}</strong>
                  </div>
                  <div>
                    <small>Sessions</small>
                    <strong>{sport.activity_count}</strong>
                  </div>
                  <div>
                    <small>Load</small>
                    <strong>{formatNumber(sport.total_training_load)}</strong>
                  </div>
                </div>
                <div className="metricBar">
                  <i style={{ width: `${share}%` }} />
                </div>
              </article>
            );
          })}
        </section>
      </section>
    </main>
  );
}
