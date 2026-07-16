"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-16
 * License: MIT
 */

import {
  Activity,
  BarChart3,
  Bike,
  BookOpenText,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Flag,
  LayoutDashboard,
  MessageSquareText,
  Moon,
  Pencil,
  Plus,
  RotateCcw,
  Sun,
  Target,
  TrendingUp,
  Trophy,
  Waves,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";
type Sport = "running" | "cycling" | "swimming" | "multisport";
type Priority = "A" | "B" | "C";
type GoalType = "completion" | "finish_time";
type GoalStatus = "upcoming" | "completed" | "cancelled";
type MultisportSegment = {
  sport: "swimming" | "cycling" | "running";
  distanceKm: string;
};

type RaceGoal = {
  id: number;
  title: string;
  eventDate: string;
  sport: Sport;
  eventFormat: string;
  segments: MultisportSegment[];
  distanceKm: string;
  priority: Priority;
  goalType: GoalType;
  targetTime: string;
  notes: string;
  status: GoalStatus;
};

type ApiRaceGoal = {
  id: number;
  title: string;
  event_date: string;
  sport: Sport;
  distance_meters: number | null;
  multisport_format: string | null;
  priority: Priority;
  goal_type: GoalType;
  target_duration_seconds: number | null;
  notes: string;
  status: GoalStatus;
  segments: { sport: MultisportSegment["sport"]; distance_meters: number | null }[];
};

type GoalForm = Omit<RaceGoal, "id" | "status">;

const SPORT_LABELS: Record<Sport, string> = {
  running: "Running",
  cycling: "Cycling",
  swimming: "Swimming",
  multisport: "Multisport",
};

const SPORT_ICONS = {
  running: Activity,
  cycling: Bike,
  swimming: Waves,
  multisport: Trophy,
};

const MULTISPORT_FORMATS = [
  { value: "triathlon_sprint", label: "Triathlon sprint" },
  { value: "triathlon_olympic", label: "Olympic-distance triathlon" },
  { value: "half_iron_distance", label: "Half iron-distance / 70.3" },
  { value: "full_iron_distance", label: "Full iron-distance" },
  { value: "other_multisport", label: "Other multisport event" },
];

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isoDate(date: Date) {
  const localDate = new Date(date);
  localDate.setHours(12, 0, 0, 0);
  return localDate.toISOString().slice(0, 10);
}

function parseIsoDate(value: string) {
  return new Date(`${value}T12:00:00`);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function emptyGoalForm(): GoalForm {
  return {
    title: "",
    eventDate: isoDate(addDays(new Date(), 90)),
    sport: "running",
    eventFormat: "",
    segments: [],
    distanceKm: "",
    priority: "A",
    goalType: "completion",
    targetTime: "",
    notes: "",
  };
}

function durationToText(durationSeconds: number | null) {
  if (durationSeconds === null) return "";
  const hours = Math.floor(durationSeconds / 3600);
  const minutes = Math.floor((durationSeconds % 3600) / 60);
  const seconds = durationSeconds % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function durationToSeconds(value: string) {
  const parts = value.split(":").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part) || part < 0)) return null;
  return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function kilometersToMeters(value: string) {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return null;
  const kilometers = Number(normalized);
  if (!Number.isFinite(kilometers) || kilometers <= 0) return undefined;
  return Math.round(kilometers * 1000);
}

function goalFromApi(goal: ApiRaceGoal): RaceGoal {
  return {
    id: goal.id,
    title: goal.title,
    eventDate: goal.event_date,
    sport: goal.sport,
    eventFormat: goal.multisport_format ?? "",
    segments: goal.segments.map((segment) => ({
      sport: segment.sport,
      distanceKm: segment.distance_meters === null ? "" : String(segment.distance_meters / 1000),
    })),
    distanceKm: goal.distance_meters === null ? "" : String(goal.distance_meters / 1000),
    priority: goal.priority,
    goalType: goal.goal_type,
    targetTime: durationToText(goal.target_duration_seconds),
    notes: goal.notes,
    status: goal.status,
  };
}

function goalToForm(goal: RaceGoal): GoalForm {
  return {
    title: goal.title,
    eventDate: goal.eventDate,
    sport: goal.sport,
    eventFormat: goal.eventFormat,
    segments: goal.segments,
    distanceKm: goal.distanceKm,
    priority: goal.priority,
    goalType: goal.goalType,
    targetTime: goal.targetTime,
    notes: goal.notes,
  };
}

function formatEventDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parseIsoDate(value));
}

function formatMonth(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(date);
}

function daysUntil(value: string) {
  const today = parseIsoDate(isoDate(new Date()));
  const eventDate = parseIsoDate(value);
  return Math.round((eventDate.getTime() - today.getTime()) / 86_400_000);
}

function goalTarget(goal: Pick<RaceGoal, "goalType" | "targetTime">) {
  return goal.goalType === "finish_time" && goal.targetTime
    ? `Target ${goal.targetTime}`
    : "Finish the event";
}

function goalDistance(distanceKm: string) {
  return distanceKm ? `${distanceKm} km` : "Distance not set";
}

function multisportFormat(goal: Pick<RaceGoal, "sport" | "eventFormat">) {
  if (goal.sport !== "multisport") {
    return null;
  }
  return (
    MULTISPORT_FORMATS.find((format) => format.value === goal.eventFormat)?.label ??
    "Multisport event"
  );
}

function segmentSummary(goal: Pick<RaceGoal, "segments" | "sport">) {
  if (goal.sport !== "multisport" || goal.segments.length === 0) {
    return null;
  }
  return goal.segments
    .filter((segment) => segment.distanceKm)
    .map((segment) => `${SPORT_LABELS[segment.sport]} ${segment.distanceKm} km`)
    .join(" · ");
}

function daysLabel(value: string) {
  const days = daysUntil(value);
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "1 day to go";
  }
  return `${days} days to go`;
}

export default function GoalsPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const [goals, setGoals] = useState<RaceGoal[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<GoalForm>(emptyGoalForm);
  const [message, setMessage] = useState("Loading your goals");
  const [busy, setBusy] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    void loadGoals();
  }, []);

  const upcomingGoals = useMemo(
    () =>
      goals
        .filter((goal) => goal.status === "upcoming")
        .sort((left, right) => left.eventDate.localeCompare(right.eventDate)),
    [goals],
  );
  const historicalGoals = useMemo(
    () => goals.filter((goal) => goal.status !== "upcoming"),
    [goals],
  );
  const primaryGoal = useMemo(
    () =>
      upcomingGoals.find((goal) => goal.priority === "A") ??
      upcomingGoals[0] ??
      null,
    [upcomingGoals],
  );
  const editingGoal = useMemo(
    () => goals.find((goal) => goal.id === editingId) ?? null,
    [editingId, goals],
  );
  const calendarDays = useMemo(() => {
    const firstDay = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 1);
    const mondayOffset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = new Date(
      calendarMonth.getFullYear(),
      calendarMonth.getMonth() + 1,
      0,
    ).getDate();
    const cells = Array.from({ length: 42 }, (_, index) => index - mondayOffset + 1);
    return cells.map((day) => {
      if (day < 1 || day > daysInMonth) {
        return null;
      }
      return new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day);
    });
  }, [calendarMonth]);

  function updateForm<K extends keyof GoalForm>(field: K, value: GoalForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateSegment(index: number, distanceKm: string) {
    setForm((current) => ({
      ...current,
      segments: current.segments.map((segment, segmentIndex) =>
        segmentIndex === index ? { ...segment, distanceKm } : segment,
      ),
    }));
  }

  function updateSport(sport: Sport) {
    setForm((current) => ({
      ...current,
      sport,
      eventFormat: sport === "multisport" ? current.eventFormat : "",
      segments:
        sport === "multisport"
          ? current.segments.length > 0
            ? current.segments
            : [
                { sport: "swimming", distanceKm: "" },
                { sport: "cycling", distanceKm: "" },
                { sport: "running", distanceKm: "" },
              ]
          : [],
    }));
  }

  function startNewGoal() {
    setEditingId(null);
    setForm(emptyGoalForm());
    setMessage("Add a race goal to your account");
  }

  function editGoal(goal: RaceGoal) {
    setEditingId(goal.id);
    setForm(goalToForm(goal));
    setMessage(`Editing ${goal.title}`);
  }

  async function loadGoals() {
    setBusy(true);
    try {
      const [upcomingResponse, historyResponse] = await Promise.all([
        fetch("/api/training/goals?status=upcoming", { cache: "no-store" }),
        fetch("/api/training/goals?status=history", { cache: "no-store" }),
      ]);
      if (!upcomingResponse.ok || !historyResponse.ok) throw new Error();
      const [upcoming, history] = (await Promise.all([
        upcomingResponse.json(),
        historyResponse.json(),
      ])) as [ApiRaceGoal[], ApiRaceGoal[]];
      setGoals([...upcoming, ...history].map(goalFromApi));
      setMessage("Goals loaded");
    } catch {
      setMessage("Could not load your goals");
    } finally {
      setBusy(false);
    }
  }

  function requestBody(status: GoalStatus, source = form) {
    const targetDurationSeconds = source.goalType === "finish_time" ? durationToSeconds(source.targetTime) : null;
    const distanceMeters = kilometersToMeters(source.distanceKm);
    if (distanceMeters === undefined) throw new Error("Distance must be a positive number");
    return {
      title: source.title,
      event_date: source.eventDate,
      sport: source.sport,
      distance_meters: distanceMeters,
      multisport_format: source.sport === "multisport" ? source.eventFormat : null,
      priority: source.priority,
      goal_type: source.goalType,
      target_duration_seconds: targetDurationSeconds,
      notes: source.notes,
      status,
      segments: source.sport === "multisport" ? source.segments.map((segment) => {
        const distanceMeters = kilometersToMeters(segment.distanceKm);
        if (distanceMeters === undefined) throw new Error("Segment distance must be a positive number");
        return {
          sport: segment.sport,
          distance_meters: distanceMeters,
        };
      }) : [],
    };
  }

  async function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const status = editingId ? goals.find((goal) => goal.id === editingId)?.status ?? "upcoming" : "upcoming";
    setBusy(true);
    try {
      const response = await fetch(editingId ? `/api/training/goals/${editingId}` : "/api/training/goals", {
        method: editingId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody(status)),
      });
      if (!response.ok) throw new Error();
      const goal = goalFromApi((await response.json()) as ApiRaceGoal);
      setGoals((current) => [...current.filter((candidate) => candidate.id !== goal.id), goal]);
      setEditingId(goal.id);
      setMessage("Goal saved");
    } catch {
      setMessage("Could not save this goal");
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(goal: RaceGoal, status: GoalStatus) {
    const goalForm = goalToForm(goal);
    setForm(goalForm);
    setBusy(true);
    try {
      const response = await fetch(`/api/training/goals/${goal.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody(status, goalForm)),
      });
      if (!response.ok) throw new Error();
      const updated = goalFromApi((await response.json()) as ApiRaceGoal);
      setGoals((current) => [...current.filter((candidate) => candidate.id !== updated.id), updated]);
      const statusMessage = {
        upcoming: `${goal.title} restored as upcoming`,
        completed: `${goal.title} marked completed`,
        cancelled: `${goal.title} cancelled`,
      };
      setMessage(statusMessage[status]);
    } catch {
      setMessage("Could not update this goal");
    } finally {
      setBusy(false);
    }
  }

  function moveMonth(offset: number) {
    setCalendarMonth(
      (current) => new Date(current.getFullYear(), current.getMonth() + offset, 1),
    );
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Goals and races controls">
        <section className="brand">
          <span className="brandMark" aria-hidden="true">
            <Flag size={24} />
          </span>
          <span>
            <h1>Personal Training AI Coach</h1>
            <p>Training intelligence console</p>
          </span>
        </section>

        <nav className="panel navPanel" aria-label="Main navigation">
          <div className="panelTitle">
            <Flag size={17} />
            <h2>Navigation</h2>
          </div>
          <Link className="navItem" href="/coach-overview">
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
          <Link className="navItem active" href="/goals" aria-current="page">
            <Flag size={16} />
            <span>Goals & races</span>
          </Link>
          <Link className="navItem" href="/nutrition-diary">
            <BookOpenText size={16} />
            <span>Food diary</span>
          </Link>
        </nav>

        <section className="panel">
          <div className="panelTitle">
            <CheckCircle2 size={17} />
            <h2>Goal storage</h2>
          </div>
          <div className={`statusLine ${message.startsWith("Could not") ? "offline" : busy ? "checking" : "online"}`}>
            {message.startsWith("Could not") ? <CircleAlert size={17} /> : <CheckCircle2 size={17} />}
            <span>{message}</span>
          </div>
          <p className="sidebarHint">
            Goals are saved for the authenticated user. Calendar activities and
            goal-aware coach analysis are coming next.
          </p>
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

      <section className="goalsShell">
        <header className="topbar">
          <div>
            <h2>Goals & races</h2>
            <p>Keep your next event visible and give your training context.</p>
          </div>
          <span className="topSignal">
            <Flag size={16} />
            Saved to your account
          </span>
        </header>

        <section className="goalHero" aria-labelledby="primary-goal-heading">
          <div className="goalHeroCopy">
            <span className="eyebrow">Primary goal</span>
            {primaryGoal ? (
              <>
                <div className="goalHeroTitle">
                  <Trophy size={25} />
                  <h3 id="primary-goal-heading">{primaryGoal.title}</h3>
                </div>
                <p>
                  {formatEventDate(primaryGoal.eventDate)} · {multisportFormat(primaryGoal) ?? SPORT_LABELS[primaryGoal.sport]} · {goalDistance(primaryGoal.distanceKm)}
                </p>
                <div className="goalHeroMeta">
                  <span className="priorityBadge priorityA">Priority {primaryGoal.priority}</span>
                  <strong>{daysLabel(primaryGoal.eventDate)}</strong>
                  <span>{goalTarget(primaryGoal)}</span>
                </div>
              </>
            ) : (
              <>
                <h3 id="primary-goal-heading">No primary goal yet</h3>
                <p>Add an upcoming event when you want training context.</p>
              </>
            )}
          </div>
          <div className="goalHeroBoundary">
            <Target size={20} />
            <div>
              <strong>Context, not a verdict</strong>
              <p>
                This page does not calculate readiness or recommend a training
                plan.
              </p>
            </div>
          </div>
        </section>

        <div className="goalWorkspace">
          <section className="goalListPanel" aria-labelledby="upcoming-goals-heading">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">Your calendar</span>
                <h3 id="upcoming-goals-heading">Upcoming goals</h3>
              </div>
              <span className="goalListCount">{upcomingGoals.length} upcoming</span>
            </div>

            <div className="goalCards">
              {upcomingGoals.map((goal) => {
                const SportIcon = SPORT_ICONS[goal.sport];
                return (
                  <article className="goalCard" key={goal.id}>
                    <span className={`goalSportIcon ${goal.sport}`}>
                      <SportIcon size={20} />
                    </span>
                    <div className="goalCardBody">
                      <div className="goalCardHeading">
                        <div>
                          <h4>{goal.title}</h4>
                          <p>{formatEventDate(goal.eventDate)}</p>
                        </div>
                        <span className={`priorityBadge priority${goal.priority}`}>
                          {goal.priority}
                        </span>
                      </div>
                      <div className="goalFacts">
                        <span>{multisportFormat(goal) ?? SPORT_LABELS[goal.sport]}</span>
                        <span>{goalDistance(goal.distanceKm)}</span>
                        <span>{goalTarget(goal)}</span>
                      </div>
                      {segmentSummary(goal) ? <p className="segmentSummary">{segmentSummary(goal)}</p> : null}
                      <div className="goalCardFooter">
                        <strong>{daysLabel(goal.eventDate)}</strong>
                        <button className="textAction" type="button" onClick={() => editGoal(goal)}>
                          <Pencil size={15} />
                          Edit
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="historySection">
              <div className="historyHeader">
                <h4>History</h4>
                <span>{historicalGoals.length} event</span>
              </div>
              {historicalGoals.map((goal) => (
                <div className="historyGoal" key={goal.id}>
                  <span className={`goalSportIcon ${goal.sport}`}>
                    <CheckCircle2 size={17} />
                  </span>
                  <span>
                    <strong>{goal.title}</strong>
                    <small>{formatEventDate(goal.eventDate)} · {goal.status}</small>
                  </span>
                  <button className="textAction" type="button" onClick={() => editGoal(goal)}>
                    <Pencil size={15} />
                    View
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="goalFormPanel" aria-labelledby="goal-form-heading">
            <div className="sectionHeader">
              <div>
                <span className="eyebrow">{editingId ? "Edit goal" : "New goal"}</span>
                <h3 id="goal-form-heading">
                  {editingId ? "Refine your event context" : "What are you aiming for?"}
                </h3>
              </div>
              {editingId ? (
                <button className="iconButton" type="button" onClick={startNewGoal} aria-label="Create a new goal">
                  <Plus size={18} />
                </button>
              ) : null}
            </div>

            <form className="goalForm" onSubmit={saveGoal}>
              <label className="field fieldWide">
                <span>Event name</span>
                <input
                  required
                  placeholder="e.g. Rome Marathon"
                  value={form.title}
                  onChange={(event) => updateForm("title", event.target.value)}
                />
              </label>
              <label className="field">
                <span>Event date</span>
                <input
                  required
                  type="date"
                  value={form.eventDate}
                  onChange={(event) => updateForm("eventDate", event.target.value)}
                />
              </label>
              <label className="field">
                <span>Sport</span>
                <select value={form.sport} onChange={(event) => updateSport(event.target.value as Sport)}>
                  <option value="running">Running</option>
                  <option value="cycling">Cycling</option>
                  <option value="swimming">Swimming</option>
                  <option value="multisport">Multisport</option>
                </select>
              </label>
              <label className="field">
                <span>Priority</span>
                <select value={form.priority} onChange={(event) => updateForm("priority", event.target.value as Priority)}>
                  <option value="A">A · main goal</option>
                  <option value="B">B · important</option>
                  <option value="C">C · supporting</option>
                </select>
              </label>
              <label className="field">
                <span>{form.sport === "multisport" ? "Total distance (km, optional)" : "Distance (km, optional)"}</span>
                <input
                  inputMode="decimal"
                  pattern="[0-9]+([,.][0-9]+)?"
                  placeholder="42.195 or 42,195"
                  type="text"
                  value={form.distanceKm}
                  onChange={(event) => updateForm("distanceKm", event.target.value)}
                />
              </label>
              {form.sport === "multisport" ? (
                <>
                  <label className="field fieldWide">
                    <span>Multisport format</span>
                    <select
                      required
                      value={form.eventFormat}
                      onChange={(event) => updateForm("eventFormat", event.target.value)}
                    >
                      <option value="">Select the event format</option>
                      {MULTISPORT_FORMATS.map((format) => (
                        <option key={format.value} value={format.value}>
                          {format.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <fieldset className="multisportSegments fieldWide">
                    <legend>Disciplines and distances</legend>
                    <p>Optional distances make the event context clearer; they are not a training plan.</p>
                    {form.segments.map((segment, index) => {
                      const SegmentIcon = SPORT_ICONS[segment.sport];
                      return (
                        <label className="segmentField" key={segment.sport}>
                          <span><SegmentIcon size={15} /> {SPORT_LABELS[segment.sport]}</span>
                          <input
                            inputMode="decimal"
                            pattern="[0-9]+([,.][0-9]+)?"
                            placeholder="km, e.g. 1.9"
                            type="text"
                            value={segment.distanceKm}
                            onChange={(event) => updateSegment(index, event.target.value)}
                          />
                        </label>
                      );
                    })}
                  </fieldset>
                </>
              ) : null}
              <fieldset className="goalTypeFieldset fieldWide">
                <legend>Goal</legend>
                <div className="goalTypeChoices">
                  <label className={form.goalType === "completion" ? "goalTypeChoice active" : "goalTypeChoice"}>
                    <input
                      checked={form.goalType === "completion"}
                      name="goal-type"
                      type="radio"
                      onChange={() => updateForm("goalType", "completion")}
                    />
                    <span>
                      <strong>Finish the event</strong>
                      <small>Keep the focus on the experience.</small>
                    </span>
                  </label>
                  <label className={form.goalType === "finish_time" ? "goalTypeChoice active" : "goalTypeChoice"}>
                    <input
                      checked={form.goalType === "finish_time"}
                      name="goal-type"
                      type="radio"
                      onChange={() => updateForm("goalType", "finish_time")}
                    />
                    <span>
                      <strong>Finish within a time</strong>
                      <small>Add a personal target without a prediction.</small>
                    </span>
                  </label>
                </div>
              </fieldset>
              {form.goalType === "finish_time" ? (
                <label className="field fieldWide">
                  <span>Target finish time</span>
                  <input
                    pattern="[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    placeholder="03:45:00"
                    required
                    value={form.targetTime}
                    onChange={(event) => updateForm("targetTime", event.target.value)}
                  />
                </label>
              ) : null}
              <label className="field fieldWide">
                <span>Notes (optional)</span>
                <textarea
                  placeholder="What would make this event meaningful?"
                  rows={3}
                  value={form.notes}
                  onChange={(event) => updateForm("notes", event.target.value)}
                />
              </label>
              <div className="formActions fieldWide">
                <button className="primaryAction" type="submit">
                  <Check size={18} />
                  {editingId ? "Save changes" : "Add race goal"}
                </button>
                {editingGoal?.status === "upcoming" ? (
                  <>
                    <button
                      className="secondaryAction"
                      type="button"
                      onClick={() => {
                        const goal = goals.find((candidate) => candidate.id === editingId);
                        if (goal) updateStatus(goal, "completed");
                      }}
                    >
                      <CheckCircle2 size={18} />
                      Completed
                    </button>
                    <button
                      className="dangerAction"
                      type="button"
                      onClick={() => {
                        const goal = goals.find((candidate) => candidate.id === editingId);
                        if (goal) updateStatus(goal, "cancelled");
                      }}
                    >
                      <X size={18} />
                      Cancel event
                    </button>
                  </>
                ) : editingGoal ? (
                  <button
                    className="secondaryAction"
                    type="button"
                    onClick={() => updateStatus(editingGoal, "upcoming")}
                  >
                    <RotateCcw size={18} />
                    Restore as upcoming
                  </button>
                ) : null}
              </div>
              <p className="prototypeNote fieldWide">{message}</p>
            </form>
          </section>
        </div>

        <section className="calendarPanel" aria-labelledby="calendar-heading">
          <div className="sectionHeader calendarHeader">
            <div>
              <span className="eyebrow">Race calendar</span>
              <h3 id="calendar-heading">{formatMonth(calendarMonth)}</h3>
            </div>
            <div className="calendarActions">
              <button className="iconButton" type="button" onClick={() => moveMonth(-1)} aria-label="Previous month">
                <ChevronLeft size={18} />
              </button>
              <button className="secondaryAction compactAction" type="button" onClick={() => setCalendarMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}>
                Today
              </button>
              <button className="iconButton" type="button" onClick={() => moveMonth(1)} aria-label="Next month">
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
          <div className="calendarLegend" aria-label="Calendar legend">
            <span><i className="raceMarker" /> Race goal</span>
            <span><CalendarDays size={14} /> Activity markers will appear when the calendar data API is available</span>
          </div>
          <div className="calendarGrid" role="grid" aria-label={`Race calendar for ${formatMonth(calendarMonth)}`}>
            {WEEKDAY_LABELS.map((label) => <span className="calendarWeekday" key={label}>{label}</span>)}
            {calendarDays.map((date, index) => {
              if (!date) {
                return <div className="calendarCell empty" key={`empty-${index}`} />;
              }
              const dateValue = isoDate(date);
              const goalsForDay = goals.filter((goal) => goal.eventDate === dateValue);
              const isToday = dateValue === isoDate(new Date());
              return (
                <div className={`calendarCell${isToday ? " today" : ""}`} key={dateValue} role="gridcell">
                  <span className="calendarDay">{date.getDate()}</span>
                  <div className="calendarEntries">
                    {goalsForDay.map((goal) => (
                      <button className={`calendarRace priority${goal.priority}`} key={goal.id} type="button" onClick={() => editGoal(goal)}>
                        <Flag size={12} />
                        {goal.title}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </section>
    </main>
  );
}
