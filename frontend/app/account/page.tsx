"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-10
 * License: MIT
 */

import { CheckCircle2, KeyRound, Save, Trash2, Wifi } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

type CredentialStatus = {
  configured: boolean;
  garmin_username: string | null;
  updated_at: string | null;
};

type ErrorResponse = {
  message?: string;
};

export default function AccountPage() {
  const [status, setStatus] = useState<CredentialStatus | null>(null);
  const [garminUsername, setGarminUsername] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [message, setMessage] = useState("Loading Garmin credential status");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadStatus();
  }, []);

  async function loadStatus() {
    setBusy(true);
    try {
      const response = await fetch("/api/account/garmin-credentials", {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Status API returned HTTP ${response.status}`);
      }
      const body = (await response.json()) as CredentialStatus;
      setStatus(body);
      setGarminUsername(body.garmin_username ?? "");
      setMessage(
        body.configured
          ? "Garmin credentials are configured"
          : "Garmin credentials are not configured",
      );
    } catch {
      setMessage("Could not load Garmin credential status");
    } finally {
      setBusy(false);
    }
  }

  async function saveCredentials(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("Saving Garmin credentials");
    try {
      const response = await fetch("/api/account/garmin-credentials", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          garmin_username: garminUsername,
          garmin_password: garminPassword,
        }),
      });
      if (!response.ok) {
        throw new Error(`Save API returned HTTP ${response.status}`);
      }
      const body = (await response.json()) as CredentialStatus;
      setStatus(body);
      setGarminPassword("");
      setMessage("Garmin credentials saved");
    } catch {
      setMessage("Could not save Garmin credentials");
    } finally {
      setBusy(false);
    }
  }

  async function testCredentials() {
    setBusy(true);
    setMessage("Testing Garmin login");
    try {
      const response = await fetch("/api/account/garmin-credentials/test", {
        method: "POST",
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as ErrorResponse | null;
        throw new Error(body?.message ?? `Test API returned HTTP ${response.status}`);
      }
      setMessage("Garmin login test passed");
    } catch (caughtError) {
      setMessage((caughtError as Error).message || "Garmin login test failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteCredentials() {
    setBusy(true);
    setMessage("Deleting Garmin credentials");
    try {
      const response = await fetch("/api/account/garmin-credentials", {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Delete API returned HTTP ${response.status}`);
      }
      setStatus({ configured: false, garmin_username: null, updated_at: null });
      setGarminUsername("");
      setGarminPassword("");
      setMessage("Garmin credentials deleted");
    } catch {
      setMessage("Could not delete Garmin credentials");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <KeyRound size={22} />
          </div>
          <div>
            <h1>Account</h1>
            <p>Garmin access</p>
          </div>
        </div>

        <div className="panel">
          <div className="panelTitle">
            <CheckCircle2 size={18} />
            <h2>Status</h2>
          </div>
          <div className="statusLine online">
            <CheckCircle2 size={16} />
            <span>{message}</span>
          </div>
          <Link className="sideLink" href="/">
            Chat
          </Link>
          <Link className="sideLink" href="/nutrition-diary">
            Nutrition diary
          </Link>
        </div>
      </aside>

      <main className="diaryShell">
        <header className="topbar">
          <div>
            <h2>Garmin Credentials</h2>
            <p>
              {status?.configured
                ? `Configured for ${status.garmin_username}`
                : "No Garmin account is configured for this user"}
            </p>
          </div>
          <div className="topSignal">
            <KeyRound size={16} />
            <span>{status?.configured ? "Configured" : "Missing"}</span>
          </div>
        </header>

        <section className="diaryPanel">
          <div className="diaryPanelHeader">
            <div className="diaryIcon">
              <Wifi size={20} />
            </div>
            <div>
              <h3>Garmin Connect</h3>
              <p>Credentials are stored encrypted in the local backend database.</p>
            </div>
          </div>

          <form className="diaryForm" onSubmit={saveCredentials}>
            <label className="field">
              <span>Username or email</span>
              <input
                autoComplete="username"
                disabled={busy}
                onChange={(event) => setGarminUsername(event.target.value)}
                value={garminUsername}
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                autoComplete="current-password"
                disabled={busy}
                onChange={(event) => setGarminPassword(event.target.value)}
                type="password"
                value={garminPassword}
              />
            </label>
            <div className="accountActions">
              <button className="primaryAction" disabled={busy} type="submit">
                <Save size={18} />
                Save
              </button>
              <button
                className="secondaryAction"
                disabled={busy || !status?.configured}
                onClick={testCredentials}
                type="button"
              >
                <Wifi size={18} />
                Test
              </button>
              <button
                className="dangerAction"
                disabled={busy || !status?.configured}
                onClick={deleteCredentials}
                type="button"
              >
                <Trash2 size={18} />
                Delete
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
