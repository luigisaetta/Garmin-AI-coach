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
type Sport = "running" | "cycling" | "swimming";
type Priority = "A" | "B" | "C";
type GoalType = "completion" | "finish_time";
type GoalStatus = "upcoming" | "completed" | "cancelled";

type RaceGoal = {
  id: string;
  title: string;
  eventDate: string;
  sport: Sport;
  distanceKm: string;
  priority: Priority;
  goalType: GoalType;
  targetTime: string;
  notes: string;
  status: GoalStatus;
};

type GoalForm = Omit<RaceGoal, "id" | "status">;

const SPORT_LABELS: Record<Sport, string> = {
  running: "Running",
  cycling: "Cycling",
  swimming: "Swimming",
};

const SPORT_ICONS = {
  running: Activity,
  cycling: Bike,
  swimming: Waves,
};

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
    distanceKm: "",
    priority: "A",
    goalType: "completion",
    targetTime: "",
    notes: "",
  };
}

function initialGoals(): RaceGoal[] {
  const today = new Date();
  return [
    {
      id: "rome-marathon",
      title: "Rome Marathon",
      eventDate: isoDate(addDays(today, 94)),
      sport: "running",
      distanceKm: "42.195",
      priority: "A",
      goalType: "finish_time",
      targetTime: "03:45:00",
      notes: "First marathon with a time target.",
      status: "upcoming",
    },
    {
      id: "gran-fondo",
      title: "Spring Gran Fondo",
      eventDate: isoDate(addDays(today, 43)),
      sport: "cycling",
      distanceKm: "120",
      priority: "B",
      goalType: "completion",
      targetTime: "",
      notes: "A long endurance day with friends.",
      status: "upcoming",
    },
    {
      id: "lake-swim",
      title: "Lake Swim",
      eventDate: isoDate(addDays(today, 168)),
      sport: "swimming",
      distanceKm: "3",
      priority: "C",
      goalType: "completion",
      targetTime: "",
      notes: "",
      status: "upcoming",
    },
    {
      id: "city-half",
      title: "City Half Marathon",
      eventDate: isoDate(addDays(today, -61)),
      sport: "running",
      distanceKm: "21.097",
      priority: "B",
      goalType: "finish_time",
      targetTime: "01:48:00",
      notes: "Completed as a controlled race effort.",
      status: "completed",
    },
  ];
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

function calendarActivities(year: number, month: number) {
  return [4, 8, 12, 18, 23, 27]
    .filter((day) => day <= new Date(year, month + 1, 0).getDate())
    .map((day) => ({
      date: isoDate(new Date(year, month, day)),
      label: day === 12 || day === 27 ? "Long run" : "Workout completed",
    }));
}

export default function GoalsPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const [goals, setGoals] = useState<RaceGoal[]>(initialGoals);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<GoalForm>(emptyGoalForm);
  const [message, setMessage] = useState("Prototype data — not saved to your account");
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

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
  const activities = useMemo(
    () => calendarActivities(calendarMonth.getFullYear(), calendarMonth.getMonth()),
    [calendarMonth],
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

  function startNewGoal() {
    setEditingId(null);
    setForm(emptyGoalForm());
    setMessage("Add a race goal to this prototype");
  }

  function editGoal(goal: RaceGoal) {
    const { id: _id, status: _status, ...goalForm } = goal;
    setEditingId(goal.id);
    setForm(goalForm);
    setMessage(`Editing ${goal.title} in this prototype`);
  }

  function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const goal: RaceGoal = {
      ...form,
      id: editingId ?? `goal-${Date.now()}`,
      status: editingId
        ? goals.find((candidate) => candidate.id === editingId)?.status ?? "upcoming"
        : "upcoming",
    };
    setGoals((current) =>
      editingId
        ? current.map((candidate) => (candidate.id === editingId ? goal : candidate))
        : [...current, goal],
    );
    setEditingId(goal.id);
    setMessage("Saved in this browser prototype only");
  }

  function updateStatus(goal: RaceGoal, status: GoalStatus) {
    setGoals((current) =>
      current.map((candidate) =>
        candidate.id === goal.id ? { ...candidate, status } : candidate,
      ),
    );
    setMessage(
      status === "completed"
        ? `${goal.title} marked completed in this prototype`
        : `${goal.title} cancelled in this prototype`,
    );
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
            <CircleAlert size={17} />
            <h2>Prototype status</h2>
          </div>
          <div className="statusLine checking">
            <CircleAlert size={17} />
            <span>Sample data only</span>
          </div>
          <p className="sidebarHint">
            Add and edit goals to test the experience. No goal is saved or sent
            to the assistant yet.
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
            Prototype · sample data
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
                  {formatEventDate(primaryGoal.eventDate)} · {SPORT_LABELS[primaryGoal.sport]} · {goalDistance(primaryGoal.distanceKm)}
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
                This prototype does not calculate readiness or recommend a
                training plan.
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
              <button className="analysisButton" type="button" onClick={startNewGoal}>
                <Plus size={17} />
                Add race goal
              </button>
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
                        <span>{SPORT_LABELS[goal.sport]}</span>
                        <span>{goalDistance(goal.distanceKm)}</span>
                        <span>{goalTarget(goal)}</span>
                      </div>
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
                <select value={form.sport} onChange={(event) => updateForm("sport", event.target.value as Sport)}>
                  <option value="running">Running</option>
                  <option value="cycling">Cycling</option>
                  <option value="swimming">Swimming</option>
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
                <span>Distance (km, optional)</span>
                <input
                  inputMode="decimal"
                  min="0"
                  placeholder="42.195"
                  type="number"
                  value={form.distanceKm}
                  onChange={(event) => updateForm("distanceKm", event.target.value)}
                />
              </label>
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
                {editingId ? (
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
            <span><i className="activityMarker" /> Completed activity</span>
            <span><CalendarDays size={14} /> Activities are shown, not planned sessions</span>
          </div>
          <div className="calendarGrid" role="grid" aria-label={`Race calendar for ${formatMonth(calendarMonth)}`}>
            {WEEKDAY_LABELS.map((label) => <span className="calendarWeekday" key={label}>{label}</span>)}
            {calendarDays.map((date, index) => {
              if (!date) {
                return <div className="calendarCell empty" key={`empty-${index}`} />;
              }
              const dateValue = isoDate(date);
              const goalsForDay = goals.filter((goal) => goal.eventDate === dateValue);
              const activitiesForDay = activities.filter((activity) => activity.date === dateValue);
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
                    {activitiesForDay.map((activity) => (
                      <span className="calendarActivity" key={activity.label}>
                        <Activity size={12} />
                        {activity.label}
                      </span>
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
