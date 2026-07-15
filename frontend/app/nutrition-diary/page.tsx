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
  BookOpenText,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  FileText,
  LayoutDashboard,
  MessageSquareText,
  Moon,
  NotebookPen,
  Save,
  Soup,
  Sun,
  TrendingUp,
  UploadCloud,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Theme = "light" | "black";
type DiaryState = "loading" | "editing" | "saved" | "missing" | "error";
type PlanState = "loading" | "missing" | "ready" | "uploading" | "error";

type NutritionDiaryEntry = {
  id: number;
  entry_date: string;
  training_type: string;
  meals_text: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

type NutritionPlan = {
  id: number;
  original_filename: string;
  content_type: string;
  file_sha256: string;
  extracted_text: string;
  uploaded_at: string;
  updated_at: string;
};

type NutritionDiaryRewrite = {
  rewritten_meals_text: string;
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

const EMPTY_DAY_MEAL_TEMPLATE = [
  "Breakfast:",
  "",
  "Morning snack:",
  "",
  "Lunch:",
  "",
  "Afternoon snack:",
  "",
  "Dinner:",
].join("\n");

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
  const [planState, setPlanState] = useState<PlanState>("loading");
  const [nutritionPlan, setNutritionPlan] = useState<NutritionPlan | null>(null);
  const [planMessage, setPlanMessage] = useState("Checking nutrition plan");
  const [selectedPlanFile, setSelectedPlanFile] = useState<File | null>(null);
  const [isRewritingMeals, setIsRewritingMeals] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCurrentPlan() {
      setPlanState("loading");
      setPlanMessage("Checking nutrition plan");

      try {
        const response = await fetch("/api/nutrition/plan/current", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (response.status === 404) {
          setNutritionPlan(null);
          setPlanState("missing");
          setPlanMessage("No nutrition plan loaded");
          return;
        }

        if (!response.ok) {
          throw new Error(`Nutrition plan API returned HTTP ${response.status}`);
        }

        const plan = (await response.json()) as NutritionPlan;
        setNutritionPlan(plan);
        setPlanState("ready");
        setPlanMessage("Nutrition plan loaded");
      } catch (caughtError) {
        if ((caughtError as Error).name === "AbortError") {
          return;
        }
        setPlanState("error");
        setPlanMessage("Could not load nutrition plan");
      }
    }

    loadCurrentPlan();
    return () => controller.abort();
  }, []);

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
          setMeals(EMPTY_DAY_MEAL_TEMPLATE);
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

  async function saveDiaryEntry() {
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

  async function rewriteMealText() {
    const trimmedMeals = meals.trim();
    if (!trimmedMeals) {
      setDiaryState("error");
      setStatusMessage("Meal description is required");
      return;
    }

    setIsRewritingMeals(true);
    setStatusMessage("Rewriting diary text");

    try {
      const response = await fetch(
        `/api/nutrition/diary-entries/${encodeURIComponent(diaryDate)}/rewrite`,
        {
          method: "POST",
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
        throw new Error(`Diary rewrite API returned HTTP ${response.status}`);
      }

      const rewrite = (await response.json()) as NutritionDiaryRewrite;
      setMeals(rewrite.rewritten_meals_text);
      setDiaryState("editing");
      setStatusMessage("AI rewrite ready to review");
    } catch {
      setDiaryState("error");
      setStatusMessage("Could not rewrite this diary text");
    } finally {
      setIsRewritingMeals(false);
    }
  }

  async function handlePlanUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPlanFile) {
      setPlanState("error");
      setPlanMessage("Choose a PDF nutrition plan first");
      return;
    }

    setPlanState("uploading");
    setPlanMessage("Uploading and extracting PDF text");

    const formData = new FormData();
    formData.append("file", selectedPlanFile);

    try {
      const response = await fetch("/api/nutrition/plan", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Nutrition plan API returned HTTP ${response.status}`);
      }

      const plan = (await response.json()) as NutritionPlan;
      setNutritionPlan(plan);
      setSelectedPlanFile(null);
      setPlanState("ready");
      setPlanMessage("Nutrition plan uploaded");
    } catch {
      setPlanState("error");
      setPlanMessage("Could not extract text from this PDF");
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
            <h1>Personal Training AI Coach</h1>
            <p>Training intelligence console</p>
          </span>
        </section>

        <nav className="panel navPanel" aria-label="Main navigation">
          <div className="panelTitle">
            <BookOpenText size={17} />
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
            <FileText size={17} />
            <h2>Nutrition plan</h2>
          </div>
          <div
            className={`statusLine ${
              planState === "error"
                ? "offline"
                : planState === "ready"
                  ? "online"
                  : "checking"
            }`}
          >
            {planState === "ready" ? (
              <CheckCircle2 size={17} />
            ) : (
              <FileText size={17} />
            )}
            <span>{planMessage}</span>
          </div>
          {nutritionPlan ? (
            <div className="planSummary">
              <strong>{nutritionPlan.original_filename}</strong>
              <span>
                {nutritionPlan.extracted_text.length.toLocaleString("en-US")} extracted
                characters
              </span>
            </div>
          ) : null}
          <form className="sidebarUploadForm" onSubmit={handlePlanUpload}>
            <label className="sidebarFileField">
              <span>PDF file</span>
              <input
                accept="application/pdf"
                type="file"
                onChange={(event) => {
                  setSelectedPlanFile(event.target.files?.[0] ?? null);
                  setPlanMessage("Ready to upload selected PDF");
                  setPlanState(nutritionPlan ? "ready" : "missing");
                }}
              />
            </label>

            <button
              className="sidebarAction"
              disabled={!selectedPlanFile || planState === "uploading"}
              type="submit"
            >
              <UploadCloud size={16} />
              <span>{nutritionPlan ? "Replace plan" : "Upload plan"}</span>
            </button>
          </form>
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
          <div className="diaryForm">
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

              <div className="formActions">
                <button
                  className="secondaryAction"
                  disabled={diaryState === "loading" || isRewritingMeals}
                  type="button"
                  onClick={() => {
                    void rewriteMealText();
                  }}
                >
                  <WandSparkles size={17} />
                  <span>{isRewritingMeals ? "Rewriting" : "Rewrite with AI"}</span>
                </button>

                <button
                  className="primaryAction"
                  disabled={diaryState === "loading" || isRewritingMeals}
                  type="button"
                  onClick={() => {
                    void saveDiaryEntry();
                  }}
                >
                  <Save size={17} />
                  <span>{savedEntry ? "Update day" : "Save day"}</span>
                </button>
              </div>
            </section>
          </div>

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
              <div>
                <dt>Nutrition plan</dt>
                <dd>
                  {nutritionPlan
                    ? `${nutritionPlan.original_filename} loaded, ${nutritionPlan.extracted_text.length.toLocaleString("en-US")} extracted characters`
                    : "No nutrition plan loaded yet."}
                </dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>
    </main>
  );
}
