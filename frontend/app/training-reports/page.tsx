"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-08-28
 * License: MIT
 */

import {
  Activity,
  BarChart3,
  BookOpenText,
  CalendarDays,
  CircleAlert,
  FileText,
  Flag,
  LayoutDashboard,
  MessageSquareText,
  Moon,
  RefreshCcw,
  Sun,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Theme = "light" | "black";
type ReportType = "last_365_days" | "custom";
type ReportState = "idle" | "loading" | "ready" | "error";

type TrainingReport = {
  begin_date: string;
  end_date: string;
  report_type: ReportType;
  report: string;
  uncategorised_activity_count: number;
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export default function TrainingReportsPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const [reportType, setReportType] = useState<ReportType>("last_365_days");
  const [beginDate, setBeginDate] = useState("");
  const [endDate, setEndDate] = useState(todayIsoDate());
  const [reportState, setReportState] = useState<ReportState>("idle");
  const [report, setReport] = useState<TrainingReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  async function generateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setReportState("loading");
    setError(null);

    const payload =
      reportType === "last_365_days"
        ? { report_type: reportType }
        : {
            report_type: reportType,
            begin_date: beginDate,
            end_date: endDate,
          };

    try {
      const response = await fetch("/api/training/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as TrainingReport | { message?: string };
      if (!response.ok || !("report" in body)) {
        throw new Error("message" in body ? body.message : "Report unavailable");
      }
      setReport(body);
      setReportState("ready");
    } catch (requestError) {
      setReportState("error");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Report unavailable",
      );
    }
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Training report controls">
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
            <FileText size={17} />
            <h2>Navigation</h2>
          </div>
          <Link className="navItem" href="/coach-overview"><LayoutDashboard size={16} /><span>Coach overview</span></Link>
          <Link className="navItem" href="/"><MessageSquareText size={16} /><span>Coach chat</span></Link>
          <Link className="navItem" href="/training-metrics"><BarChart3 size={16} /><span>Training metrics</span></Link>
          <Link className="navItem" href="/training-trends"><TrendingUp size={16} /><span>Training trends</span></Link>
          <Link className="navItem" href="/goals"><Flag size={16} /><span>Goals & races</span></Link>
          <Link className="navItem" href="/nutrition-diary"><BookOpenText size={16} /><span>Food diary</span></Link>
          <Link className="navItem active" href="/training-reports" aria-current="page"><FileText size={16} /><span>Training reports</span></Link>
        </nav>

        <section className="panel">
          <div className="panelTitle"><CalendarDays size={17} /><h2>Report range</h2></div>
          <div className="rangePresetGrid" role="group" aria-label="Report type">
            <button className={reportType === "last_365_days" ? "active" : ""} type="button" onClick={() => setReportType("last_365_days")}>Last 365 days</button>
            <button className={reportType === "custom" ? "active" : ""} type="button" onClick={() => setReportType("custom")}>Custom range</button>
          </div>
          <form className="sidebarDateForm" onSubmit={generateReport}>
            <label><span>From</span><input type="date" disabled={reportType !== "custom"} value={beginDate} onChange={(event) => setBeginDate(event.target.value)} required={reportType === "custom"} /></label>
            <label><span>To</span><input type="date" disabled={reportType !== "custom"} value={endDate} onChange={(event) => setEndDate(event.target.value)} required={reportType === "custom"} /></label>
            <button className="sidebarAction" disabled={reportState === "loading"} type="submit"><RefreshCcw size={16} /><span>{reportState === "loading" ? "Generating…" : "Generate report"}</span></button>
          </form>
        </section>

        <section className="panel">
          <div className="panelTitle"><FileText size={17} /><h2>Method</h2></div>
          <p className="sidebarHint">Deterministic summary from Garmin activity data. Custom ranges support up to 366 days.</p>
        </section>

        <section className="panel">
          <div className="panelTitle"><Moon size={17} /><h2>Settings</h2></div>
          <div className="themeSwitch" role="group" aria-label="Theme">
            <button className={theme === "light" ? "active" : ""} type="button" onClick={() => setTheme("light")}><Sun size={16} /><span>Light</span></button>
            <button className={theme === "black" ? "active" : ""} type="button" onClick={() => setTheme("black")}><Moon size={16} /><span>Black</span></button>
          </div>
        </section>
      </aside>

      <section className="metricsShell" aria-label="Training reports">
        <header className="topbar">
          <span><h2>Training reports</h2><p>Sport-specific training summary and monthly trends.</p></span>
          <div className="topSignal"><TrendingUp size={18} /><span>Up to 366 days</span></div>
        </header>

        {error ? <div className="errorBar"><CircleAlert size={16} /> {error}</div> : null}

        <section className="reportCard">
          {reportState === "idle" ? <p>Select a period and generate a report.</p> : null}
          {reportState === "loading" ? <p>Reading Garmin activity summaries and preparing the report…</p> : null}
          {report ? <><p className="reportMeta">{report.begin_date} — {report.end_date}{report.uncategorised_activity_count > 0 ? ` · ${report.uncategorised_activity_count} attività non classificate` : ""}</p><div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report.report}</ReactMarkdown></div></> : null}
        </section>
      </section>
    </main>
  );
}
