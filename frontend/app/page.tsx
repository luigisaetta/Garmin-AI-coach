"use client";

/*
 * Author: L. Saetta
 * Version: 0.1.0
 * Last modified: 2026-07-10
 * License: MIT
 */

import {
  Activity,
  BookOpenText,
  Bot,
  CheckCircle2,
  CircleAlert,
  Hash,
  MessageSquareText,
  Moon,
  RotateCcw,
  Send,
  Settings2,
  Sparkles,
  Sun,
  TrendingUp,
  User,
  Wifi,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Theme = "light" | "black";
type Role = "user" | "assistant";
type ServiceState = "checking" | "online" | "offline";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
};

type TokenUsage = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

type AssistantStreamEvent = {
  type: "message_delta" | "message_done" | "error";
  conversation_id: string;
  delta?: string;
  answer?: string;
  token_usage?: TokenUsage;
};

const QUICK_PROMPTS = [
  "Summarise my training this week",
  "Compare this week with the previous week",
  "Which runs had unusually high heart rate?",
  "What should I watch before my next long run?",
];

const SAMPLE_METRICS = [
  { label: "Focus", value: "Endurance", tone: "teal" },
  { label: "Window", value: "Last 7 days", tone: "coral" },
  { label: "Mode", value: "Streaming", tone: "gold" },
];

function createId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }

  return `message-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

function formatTokenCount(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function parseSseBlock(block: string) {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n");

  if (!data) {
    return null;
  }

  return JSON.parse(data) as AssistantStreamEvent;
}

export default function CoachChat() {
  const [theme, setTheme] = useState<Theme>("light");
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: createId(),
      role: "assistant",
      content:
        "Ask me about recent load, workout quality, pacing, heart-rate drift, or recovery signals.",
    },
  ]);
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage>({
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  });
  const abortControllerRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const assistantMessages = useMemo(
    () => messages.filter((message) => message.role === "assistant").length,
    [messages],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      setServiceState("checking");
      try {
        const response = await fetch("/api/assistant/health", {
          cache: "no-store",
        });
        if (active) {
          setServiceState(response.ok ? "online" : "offline");
        }
      } catch {
        if (active) {
          setServiceState("offline");
        }
      }
    }

    checkHealth();
    const interval = window.setInterval(checkHealth, 30000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  function resetConversation() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setConversationId(null);
    setInput("");
    setError(null);
    setIsStreaming(false);
    setTokenUsage({
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
    });
    setMessages([
      {
        id: createId(),
        role: "assistant",
        content:
          "Ask me about recent load, workout quality, pacing, heart-rate drift, or recovery signals.",
      },
    ]);
  }

  function addTokenUsage(nextUsage?: TokenUsage) {
    if (!nextUsage) {
      return;
    }

    setTokenUsage((current) => ({
      input_tokens: current.input_tokens + nextUsage.input_tokens,
      output_tokens: current.output_tokens + nextUsage.output_tokens,
      total_tokens: current.total_tokens + nextUsage.total_tokens,
    }));
  }

  async function sendMessage(nextMessage?: string) {
    const content = (nextMessage ?? input).trim();
    if (!content || isStreaming) {
      return;
    }

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content,
    };
    const assistantMessage: ChatMessage = {
      id: createId(),
      role: "assistant",
      content: "",
    };

    const history = [...messages, userMessage]
      .filter((message) => message.content.trim().length > 0)
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setError(null);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
          messages: history,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Assistant API returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const event = parseSseBlock(block);
          if (!event) {
            continue;
          }

          if (event.conversation_id) {
            setConversationId(event.conversation_id);
          }

          if (event.type === "message_delta" && event.delta) {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessage.id
                  ? { ...message, content: message.content + event.delta }
                  : message,
              ),
            );
          }

          if (event.type === "error") {
            const message = event.delta ?? "Assistant stream failed.";
            setError(message);
            setMessages((current) =>
              current.map((chatMessage) =>
                chatMessage.id === assistantMessage.id
                  ? { ...chatMessage, content: message }
                  : chatMessage,
              ),
            );
          }

          if (event.type === "message_done") {
            addTokenUsage(event.token_usage);
            if (event.answer) {
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantMessage.id
                    ? { ...message, content: event.answer ?? message.content }
                    : message,
                ),
              );
            }
          }
        }
      }

      if (buffer.trim()) {
        const event = parseSseBlock(buffer);
        if (event?.type === "message_done") {
          addTokenUsage(event.token_usage);
          if (event.answer) {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessage.id
                  ? { ...message, content: event.answer ?? message.content }
                  : message,
              ),
            );
          }
        }
      }
    } catch (caughtError) {
      if ((caughtError as Error).name !== "AbortError") {
        setError((caughtError as Error).message);
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantMessage.id
              ? {
                  ...message,
                  content:
                    "I could not reach the assistant API. Check that FastAPI is running and try again.",
                }
              : message,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendMessage();
  }

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Assistant controls">
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
            <MessageSquareText size={17} />
            <h2>Navigation</h2>
          </div>
          <Link className="navItem active" href="/" aria-current="page">
            <MessageSquareText size={16} />
            <span>Coach chat</span>
          </Link>
          <Link className="navItem" href="/training-metrics">
            <TrendingUp size={16} />
            <span>Training metrics</span>
          </Link>
          <Link className="navItem" href="/nutrition-diary">
            <BookOpenText size={16} />
            <span>Food diary</span>
          </Link>
        </nav>

        <section className="panel">
          <div className="panelTitle">
            <Wifi size={17} />
            <h2>Service</h2>
          </div>
          <div className={`statusLine ${serviceState}`}>
            {serviceState === "online" ? (
              <CheckCircle2 size={17} />
            ) : (
              <CircleAlert size={17} />
            )}
            <span>
              {serviceState === "checking"
                ? "Checking assistant API"
                : serviceState === "online"
                  ? "Assistant API online"
                  : "Assistant API offline"}
            </span>
          </div>
          <div className="miniGrid">
            {SAMPLE_METRICS.map((metric) => (
              <div className={`metric ${metric.tone}`} key={metric.label}>
                <small>{metric.label}</small>
                <strong>{metric.value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panelTitle">
            <Hash size={17} />
            <h2>Tokens</h2>
          </div>
          <div className="miniGrid">
            <div className="metric teal">
              <small>Input</small>
              <strong>{formatTokenCount(tokenUsage.input_tokens)}</strong>
            </div>
            <div className="metric coral">
              <small>Output</small>
              <strong>{formatTokenCount(tokenUsage.output_tokens)}</strong>
            </div>
            <div className="metric gold">
              <small>Total</small>
              <strong>{formatTokenCount(tokenUsage.total_tokens)}</strong>
            </div>
          </div>
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
          <button className="resetButton" type="button" onClick={resetConversation}>
            <RotateCcw size={16} />
            <span>New chat</span>
          </button>
        </section>

        <section className="panel prompts">
          <div className="panelTitle">
            <Sparkles size={17} />
            <h2>Prompts</h2>
          </div>
          {QUICK_PROMPTS.map((prompt) => (
            <button
              className="promptButton"
              disabled={isStreaming}
              key={prompt}
              type="button"
              onClick={() => sendMessage(prompt)}
            >
              {prompt}
            </button>
          ))}
        </section>
      </aside>

      <section className="chatShell" aria-label="Conversation">
        <header className="topbar">
          <span>
            <h2>Coaching conversation</h2>
            <p>
              {assistantMessages} assistant turn
              {assistantMessages === 1 ? "" : "s"} ·{" "}
              {conversationId ? "conversation locked" : "new conversation"}
            </p>
          </span>
          <div className="topSignal">
            <TrendingUp size={18} />
            <span>Load, pace, HR, recovery</span>
          </div>
        </header>

        <div className="conversation">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <span className="avatar" aria-hidden="true">
                {message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
              </span>
              <div className="bubble">
                {message.content ? (
                  message.role === "assistant" ? (
                    <div className="markdown">
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
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    message.content
                  )
                ) : (
                  <span className="typing">
                    <i />
                    <i />
                    <i />
                  </span>
                )}
              </div>
            </article>
          ))}
          <div ref={bottomRef} />
        </div>

        {error ? <div className="errorBar">{error}</div> : null}

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            aria-label="Message"
            disabled={isStreaming}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask about your latest run, weekly load, HR drift, or recovery..."
            rows={1}
            value={input}
          />
          <button disabled={!input.trim() || isStreaming} title="Send" type="submit">
            <Send size={18} />
          </button>
        </form>
      </section>
    </main>
  );
}
