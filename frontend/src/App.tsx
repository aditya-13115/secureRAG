import {
  Database,
  FileSearch,
  Lock,
  PanelLeft,
  RotateCcw,
  Server,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  demoUsers,
} from "./data/demoUsers";

import { sendChatMessage } from "./lib/api";

import { AccessPanel } from "./components/AccessPanel";
import { ChatComposer } from "./components/ChatComposer";
import { ChatMessage } from "./components/ChatMessage";
import { SourceCard } from "./components/SourceCard";
import { TopBar } from "./components/TopBar";

import type {
  ChatResponse,
  DemoUser,
} from "./types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}

function App() {
  const [selectedUserEmail, setSelectedUserEmail] =
    useState(
      "engineer@monke.ai"
    );

  const selectedUser =
    useMemo<DemoUser>(
      () =>
        demoUsers.find(
          (user) =>
            user.email ===
            selectedUserEmail
        ) ?? demoUsers[5],
      [selectedUserEmail]
    );

  const [messages, setMessages] =
    useState<Message[]>([]);

  const [query, setQuery] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [sidebarOpen, setSidebarOpen] =
    useState(true);

  const selectedRole =
    selectedUser.role;

  function handleRoleChange(
    role: string
  ) {
    const nextUser =
      demoUsers.find(
        (user) =>
          user.role === role
      );

    if (nextUser) {
      setSelectedUserEmail(
        nextUser.email
      );
      setMessages([]);
      setError(null);
    }
  }

  function handleUserChange(
    email: string
  ) {
    setSelectedUserEmail(email);
    setMessages([]);
    setError(null);
  }

  async function handleSubmit() {
    const trimmed =
      query.trim();

    if (
      !trimmed ||
      loading
    ) {
      return;
    }

    setError(null);

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    };

    setMessages(
      (current) => [
        ...current,
        userMessage,
      ]
    );

    setQuery("");
    setLoading(true);

    try {
      const response =
        await sendChatMessage(
          selectedUser.email,
          {
            query: trimmed,
            top_k: 8,
          }
        );

      setMessages(
        (current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              response.answer,
            response,
          },
        ]
      );
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Something went wrong.";

      setError(message);
    } finally {
      setLoading(false);
    }
  }

  function clearConversation() {
    setMessages([]);
    setQuery("");
    setError(null);
  }

  return (
    <div className="h-screen overflow-hidden bg-[#080a0d] text-white">
      <TopBar
        user={selectedUser}
      />

      <div className="flex h-[calc(100vh-4rem)]">
        {/* SIDEBAR */}
        <aside
          className={`${
            sidebarOpen
              ? "w-[300px]"
              : "w-0"
          } shrink-0 overflow-hidden border-r border-white/[0.06] bg-[#0a0c0f] transition-all duration-300`}
        >
          <div className="flex h-full w-[300px] flex-col">
            <div className="flex items-center justify-between border-b border-white/[0.05] px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">
                  Security Console
                </span>
              </div>

              <button
                onClick={
                  clearConversation
                }
                className="rounded-lg p-1.5 text-white/20 transition hover:bg-white/[0.05] hover:text-white/50"
                title="Clear current session"
              >
                <RotateCcw
                  size={14}
                />
              </button>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              <AccessPanel
                selectedRole={
                  selectedRole
                }
                selectedUser={
                  selectedUser
                }
                onRoleChange={
                  handleRoleChange
                }
                onUserChange={
                  handleUserChange
                }
              />

              <div className="rounded-2xl border border-white/[0.06] bg-[#0d1014] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Lock
                    size={14}
                    className="text-white/30"
                  />

                  <span className="text-xs font-medium text-white/55">
                    Access model
                  </span>
                </div>

                <div className="space-y-2">
                  {[
                    [
                      "Identity",
                      selectedUser.email,
                    ],
                    [
                      "Role",
                      selectedUser.role,
                    ],
                    [
                      "Department",
                      selectedUser.department,
                    ],
                    [
                      "Retrieval",
                      "ACL → Hybrid RRF",
                    ],
                  ].map(
                    ([label, value]) => (
                      <div
                        key={label}
                        className="flex items-start justify-between gap-3"
                      >
                        <span className="text-[10px] text-white/20">
                          {label}
                        </span>

                        <span className="max-w-[170px] truncate text-right text-[10px] text-white/45">
                          {value}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-white/[0.06] bg-[#0d1014] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Database
                    size={14}
                    className="text-white/30"
                  />

                  <span className="text-xs font-medium text-white/55">
                    Retrieval stack
                  </span>
                </div>

                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-white/25">
                      Semantic
                    </span>
                    <span className="text-[10px] font-medium text-emerald-300/70">
                      65%
                    </span>
                  </div>

                  <div className="h-1 overflow-hidden rounded-full bg-white/[0.04]">
                    <div className="h-full w-[65%] rounded-full bg-emerald-400/60" />
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-white/25">
                      BM25
                    </span>
                    <span className="text-[10px] font-medium text-sky-300/70">
                      35%
                    </span>
                  </div>

                  <div className="h-1 overflow-hidden rounded-full bg-white/[0.04]">
                    <div className="h-full w-[35%] rounded-full bg-sky-400/60" />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-white/[0.06] bg-[#0d1014] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Server
                    size={14}
                    className="text-white/30"
                  />

                  <span className="text-xs font-medium text-white/55">
                    Runtime
                  </span>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-white/20">
                      Vector store
                    </span>
                    <span className="text-[10px] text-white/40">
                      Chroma
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-white/20">
                      Lexical
                    </span>
                    <span className="text-[10px] text-white/40">
                      SQLite FTS5
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-white/20">
                      Generation
                    </span>
                    <span className="text-[10px] text-white/40">
                      Groq
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* MAIN */}
        <main className="relative flex min-w-0 flex-1 flex-col">
          {/* mobile / desktop control */}
          <div className="absolute left-4 top-4 z-10">
            <button
              onClick={() =>
                setSidebarOpen(
                  (value) =>
                    !value
                )
              }
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.06] bg-[#0c0f13]/80 text-white/35 backdrop-blur-xl transition hover:border-white/[0.1] hover:text-white/70"
            >
              <PanelLeft
                size={15}
              />
            </button>
          </div>

          <div className="flex min-h-0 flex-1 flex-col">
            {/* EMPTY STATE */}
            {messages.length ===
              0 && (
              <div className="flex flex-1 items-center justify-center px-6">
                <div className="w-full max-w-3xl">
                  <div className="mb-10">
                    <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-400/10 bg-emerald-400/[0.06]">
                      <Sparkles
                        size={20}
                        className="text-emerald-400"
                      />
                    </div>

                    <div className="text-3xl font-semibold tracking-[-0.03em] text-white">
                      Search the company
                      <br />
                      <span className="text-white/25">
                        with permission intact.
                      </span>
                    </div>

                    <p className="mt-4 max-w-xl text-sm leading-6 text-white/30">
                      SecureRAG combines
                      semantic retrieval,
                      lexical search and
                      authorization-aware
                      context before anything
                      reaches the model.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    {[
                      {
                        icon: Lock,
                        title:
                          "Permission-aware",
                        text:
                          "Only documents available to the selected identity enter retrieval.",
                      },
                      {
                        icon: FileSearch,
                        title:
                          "Hybrid retrieval",
                        text:
                          "Semantic search and BM25 are fused with weighted RRF.",
                      },
                      {
                        icon: Sparkles,
                        title:
                          "Grounded answers",
                        text:
                          "Responses are generated from retrieved sources with citations.",
                      },
                    ].map(
                      ({
                        icon: Icon,
                        title,
                        text,
                      }) => (
                        <div
                          key={title}
                          className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4"
                        >
                          <Icon
                            size={15}
                            className="mb-3 text-white/35"
                          />
                          <div className="text-xs font-medium text-white/60">
                            {title}
                          </div>
                          <div className="mt-1.5 text-[10px] leading-5 text-white/25">
                            {text}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* MESSAGES */}
            {messages.length >
              0 && (
              <div className="flex-1 overflow-y-auto">
                <div className="mx-auto w-full max-w-4xl space-y-8 px-6 py-10">
                  {messages.map(
                    (message) => (
                      <div
                        key={message.id}
                      >
                        <ChatMessage
                          role={
                            message.role
                          }
                          content={
                            message.content
                          }
                        />

                        {message.response && (
                          <div className="ml-11 mt-4">
                            <div className="mb-2 flex items-center gap-2">
                              <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-white/20">
                                Sources
                              </span>

                              <span className="h-px flex-1 bg-white/[0.05]" />
                            </div>

                            <div className="grid gap-2">
                              {message.response.citations.map(
                                (citation) => (
                                  <SourceCard
                                    key={
                                      citation.source_id
                                    }
                                    citation={
                                      citation
                                    }
                                  />
                                )
                              )}
                            </div>

                            <div className="mt-3 flex flex-wrap gap-3 text-[10px] text-white/20">
                              <span>
                                {
                                  message
                                    .response
                                    .retrieval_count
                                }{" "}
                                sources retrieved
                              </span>

                              <span>
                                {
                                  message
                                    .response
                                    .model
                                }
                              </span>

                              <span>
                                {
                                  message
                                    .response
                                    .total_tokens
                                }{" "}
                                tokens
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  )}

                  {loading && (
                    <div className="flex gap-3">
                      <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-xl border border-emerald-400/10 bg-emerald-400/[0.06]">
                        <Sparkles
                          size={14}
                          className="animate-pulse text-emerald-400"
                        />
                      </div>

                      <div className="pt-2 text-sm text-white/30">
                        Retrieving authorized
                        context...
                      </div>
                    </div>
                  )}

                  {error && (
                    <div className="rounded-2xl border border-red-400/10 bg-red-400/[0.04] px-4 py-3 text-xs text-red-300/70">
                      {error}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* COMPOSER */}
            <div className="shrink-0 px-6 pb-5 pt-3">
              <div className="mx-auto w-full max-w-4xl">
                <ChatComposer
                  value={query}
                  disabled={loading}
                  onChange={
                    setQuery
                  }
                  onSubmit={
                    handleSubmit
                  }
                />

                <div className="mt-2 flex items-center justify-between px-1">
                  <div className="flex items-center gap-2 text-[10px] text-white/15">
                    <span className="inline-block h-1 w-1 rounded-full bg-emerald-400/60" />
                    Authenticated as{" "}
                    {selectedUser.name}
                  </div>

                  <div className="hidden text-[10px] text-white/15 sm:block">
                    SecureRAG · permission-aware
                    inference
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;