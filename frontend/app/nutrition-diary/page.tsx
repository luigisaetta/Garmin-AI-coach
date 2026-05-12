"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-05-12
 * License: MIT
 */

import {
  Activity,
  BookOpenText,
  CalendarDays,
  ClipboardList,
  MessageSquareText,
  Moon,
  NotebookPen,
  Save,
  Soup,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";
type DiaryState = "loading" | "editing" | "saved" | "missing" | "error";

type NutritionDiaryEntry = {
  id: number;
  entry_date: string;
  training_type: string;
  meals_text: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

const TRAINING_TYPES = [
  "Rest day",
  "Easy run",
  "Long run",
  "Intervals",
  "Cycling",
  "Strength",
  "Mobility",
  "Race",
  "Other",
];

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export default function NutritionDiaryDemo() {
  const [theme, setTheme] = useState<Theme>("light");
  const [diaryDate, setDiaryDate] = useState(todayIsoDate);
  const [trainingType, setTrainingType] = useState(TRAINING_TYPES[0]);
  const [meals, setMeals] = useState("");
  const [notes, setNotes] = useState("");
  const [diaryState, setDiaryState] = useState<DiaryState>("loading");
  const [savedEntry, setSavedEntry] = useState<NutritionDiaryEntry | null>(null);
  const [statusMessage, setStatusMessage] = useState("Loading diary entry");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadEntry() {
      setDiaryState("loading");
      setStatusMessage("Loading diary entry");
      setSavedEntry(null);

      try {
        const response = await fetch(
          `/api/nutrition/diary-entries/${encodeURIComponent(diaryDate)}`,
          {
            cache: "no-store",
            signal: controller.signal,
          },
        );

        if (response.status === 404) {
          setTrainingType(TRAINING_TYPES[0]);
          setMeals("");
          setNotes("");
          setDiaryState("missing");
          setStatusMessage("No entry for this date");
          return;
        }

        if (!response.ok) {
          throw new Error(`Diary API returned HTTP ${response.status}`);
        }

        const entry = (await response.json()) as NutritionDiaryEntry;
        setSavedEntry(entry);
        setTrainingType(entry.training_type);
        setMeals(entry.meals_text);
        setNotes(entry.notes);
        setDiaryState("saved");
        setStatusMessage("Saved entry loaded");
      } catch (caughtError) {
        if ((caughtError as Error).name === "AbortError") {
          return;
        }
        setDiaryState("error");
        setStatusMessage("Could not load this diary entry");
      }
    }

    loadEntry();
    return () => controller.abort();
  }, [diaryDate]);

  const formattedDate = useMemo(
    () =>
      new Intl.DateTimeFormat("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      }).format(new Date(`${diaryDate}T12:00:00`)),
    [diaryDate],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMeals = meals.trim();
    if (!trimmedMeals) {
      setDiaryState("error");
      setStatusMessage("Meal description is required");
      return;
    }

    setDiaryState("loading");
    setStatusMessage("Saving diary entry");

    try {
      const response = await fetch(
        `/api/nutrition/diary-entries/${encodeURIComponent(diaryDate)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            training_type: trainingType,
            meals_text: trimmedMeals,
            notes: notes.trim(),
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`Diary API returned HTTP ${response.status}`);
      }

      const entry = (await response.json()) as NutritionDiaryEntry;
      setSavedEntry(entry);
      setMeals(entry.meals_text);
      setNotes(entry.notes);
      setDiaryState("saved");
      setStatusMessage("Diary entry saved");
    } catch {
      setDiaryState("error");
      setStatusMessage("Could not save this diary entry");
    }
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Nutrition diary controls">
        <section className="brand">
          <span className="brandMark" aria-hidden="true">
            <Activity size={24} />
          </span>
          <span>
            <h1>Garmin AI Coach</h1>
            <p>Training intelligence console</p>
          </span>
        </section>

        <nav className="panel navPanel" aria-label="Main navigation">
          <div className="panelTitle">
            <BookOpenText size={17} />
            <h2>Navigation</h2>
          </div>
          <Link className="navItem" href="/">
            <MessageSquareText size={16} />
            <span>Coach chat</span>
          </Link>
          <Link
            className="navItem active"
            href="/nutrition-diary"
            aria-current="page"
          >
            <BookOpenText size={16} />
            <span>Food diary</span>
          </Link>
        </nav>

        <section className="panel">
          <div className="panelTitle">
            <NotebookPen size={17} />
            <h2>Food diary</h2>
          </div>
          <div
            className={`statusLine ${
              diaryState === "error" ? "offline" : "online"
            }`}
          >
            <Save size={17} />
            <span>{statusMessage}</span>
          </div>
          <div className="miniGrid">
            <div className="metric teal">
              <small>Date</small>
              <strong>{diaryDate}</strong>
            </div>
            <div className="metric coral">
              <small>Workout</small>
              <strong>{trainingType}</strong>
            </div>
            <div className="metric gold">
              <small>Status</small>
              <strong>{diaryState}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <ClipboardList size={17} />
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

      <section className="diaryShell" aria-label="Food diary">
        <header className="topbar">
          <span>
            <h2>Food diary</h2>
            <p>Daily meal notes for the future nutrition adherence workflow</p>
          </span>
          <div className="topSignal">
            <Soup size={18} />
            <span>Daily diary</span>
          </div>
        </header>

        <div className="diaryGrid">
          <form className="diaryForm" onSubmit={handleSubmit}>
            <section className="diaryPanel">
              <div className="diaryPanelHeader">
                <span className="diaryIcon" aria-hidden="true">
                  <CalendarDays size={18} />
                </span>
                <span>
                  <h3>Day and training context</h3>
                  <p>{formattedDate}</p>
                </span>
              </div>

              <label className="field">
                <span>Date</span>
                <input
                  type="date"
                  value={diaryDate}
                  onChange={(event) => setDiaryDate(event.target.value)}
                />
              </label>

              <label className="field">
                <span>Training type</span>
                <select
                  value={trainingType}
                  onChange={(event) => {
                    setTrainingType(event.target.value);
                    setDiaryState("editing");
                    setStatusMessage("Unsaved changes");
                  }}
                >
                  {TRAINING_TYPES.map((type) => (
                    <option key={type}>{type}</option>
                  ))}
                </select>
              </label>
            </section>

            <section className="diaryPanel">
              <div className="diaryPanelHeader">
                <span className="diaryIcon" aria-hidden="true">
                  <Soup size={18} />
                </span>
                <span>
                  <h3>Meal description</h3>
                  <p>Breakfast, lunch, dinner, snacks, drinks, and timing</p>
                </span>
              </div>

              <label className="field">
                <span>Meals</span>
                <textarea
                  rows={10}
                  value={meals}
                  onChange={(event) => {
                    setMeals(event.target.value);
                    setDiaryState("editing");
                    setStatusMessage("Unsaved changes");
                  }}
                  placeholder="Example: Breakfast: yogurt, oats, banana. Lunch: rice, chicken, salad. Pre-run snack: toast with honey..."
                />
              </label>

              <label className="field">
                <span>Notes</span>
                <textarea
                  rows={4}
                  value={notes}
                  onChange={(event) => {
                    setNotes(event.target.value);
                    setDiaryState("editing");
                    setStatusMessage("Unsaved changes");
                  }}
                  placeholder="Energy, hunger, digestion, hydration, race-day experiments, or questions for the nutritionist."
                />
              </label>

              <button
                className="primaryAction"
                disabled={diaryState === "loading"}
                type="submit"
              >
                <Save size={17} />
                <span>{savedEntry ? "Update day" : "Save day"}</span>
              </button>
            </section>
          </form>

          <aside className="entryPreview" aria-label="Current food diary draft">
            <div className="diaryPanelHeader">
              <span className="diaryIcon" aria-hidden="true">
                <BookOpenText size={18} />
              </span>
              <span>
                <h3>Current draft</h3>
                <p>{statusMessage}</p>
              </span>
            </div>

            <dl className="previewList">
              <div>
                <dt>Date</dt>
                <dd>{formattedDate}</dd>
              </div>
              <div>
                <dt>Training</dt>
                <dd>{trainingType}</dd>
              </div>
              <div>
                <dt>Meals</dt>
                <dd>{meals.trim() || "No meals described yet."}</dd>
              </div>
              <div>
                <dt>Notes</dt>
                <dd>{notes.trim() || "No notes added yet."}</dd>
              </div>
              {savedEntry ? (
                <div>
                  <dt>Updated</dt>
                  <dd>
                    {new Intl.DateTimeFormat("en-US", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(savedEntry.updated_at))}
                  </dd>
                </div>
              ) : null}
            </dl>
          </aside>
        </div>
      </section>
    </main>
  );
}
