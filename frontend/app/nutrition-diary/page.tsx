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
  SaveOff,
  Soup,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";

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
  const [draftState, setDraftState] = useState<"editing" | "previewed">("editing");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDraftState("previewed");
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
            <h2>Diary demo</h2>
          </div>
          <div className="statusLine online">
            <SaveOff size={17} />
            <span>Draft only, backend storage not connected</span>
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
              <strong>{draftState === "previewed" ? "Preview" : "Editing"}</strong>
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

      <section className="diaryShell" aria-label="Food diary demo">
        <header className="topbar">
          <span>
            <h2>Food diary</h2>
            <p>Daily meal notes for the future nutrition adherence workflow</p>
          </span>
          <div className="topSignal">
            <Soup size={18} />
            <span>Demo UI, no saved data</span>
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
                  onChange={(event) => {
                    setDiaryDate(event.target.value);
                    setDraftState("editing");
                  }}
                />
              </label>

              <label className="field">
                <span>Training type</span>
                <select
                  value={trainingType}
                  onChange={(event) => {
                    setTrainingType(event.target.value);
                    setDraftState("editing");
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
                    setDraftState("editing");
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
                    setDraftState("editing");
                  }}
                  placeholder="Energy, hunger, digestion, hydration, race-day experiments, or questions for the nutritionist."
                />
              </label>

              <button className="primaryAction" type="submit">
                <NotebookPen size={17} />
                <span>Preview entry</span>
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
                <p>{draftState === "previewed" ? "Ready for future save flow" : "Editing"}</p>
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
            </dl>
          </aside>
        </div>
      </section>
    </main>
  );
}
