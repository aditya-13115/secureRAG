import {
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileArchive,
  FileUp,
  History,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import {
  deleteDocument,
  getDocumentDetail,
  getIngestionStatus,
  getPolicyOptions,
  listAdminDocuments,
  reindexDocument,
  updateDocumentPolicy,
  uploadDocument,
} from "../lib/api";

import type {
  AccessScope,
  AdminDocument,
  Classification,
  DocumentDetail,
  IngestionStatus,
  PolicyOptions,
} from "../types";

interface AdminConsoleProps {
  email: string;
  onClose: () => void;
}

const CATEGORIES = [
  "finance",
  "hr",
  "technology",
  "management",
  "marketing",
  "public",
] as const;

const SCOPES: AccessScope[] = [
  "PUBLIC",
  "DEPARTMENT",
  "ROLE",
  "USER",
];

const CLASSIFICATIONS: Classification[] = [
  "PUBLIC",
  "PUBLIC_INTERNAL",
  "INTERNAL",
  "CONFIDENTIAL",
  "RESTRICTED",
];

function bytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function date(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function statusClass(status: string) {
  if (status === "INDEXED") return "text-emerald-300 bg-emerald-400/10 border-emerald-400/10";
  if (status === "INDEXING" || status === "READY_FOR_INGESTION") return "text-sky-300 bg-sky-400/10 border-sky-400/10";
  if (status === "PENDING_POLICY") return "text-amber-300 bg-amber-400/10 border-amber-400/10";
  if (status === "FAILED") return "text-red-300 bg-red-400/10 border-red-400/10";
  return "text-white/45 bg-white/[0.04] border-white/[0.05]";
}

export function AdminConsole({ email, onClose }: AdminConsoleProps) {
  const [documents, setDocuments] = useState<AdminDocument[]>([]);
  const [options, setOptions] = useState<PolicyOptions | null>(null);
  const [selected, setSelected] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("public");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [scope, setScope] = useState<AccessScope>("PUBLIC");
  const [classification, setClassification] = useState<Classification>("INTERNAL");
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [departmentIds, setDepartmentIds] = useState<number[]>([]);
  const [userIds, setUserIds] = useState<number[]>([]);
  const [ingestion, setIngestion] = useState<IngestionStatus | null>(null);

  const pendingCount = useMemo(
    () => documents.filter((document) => document.status === "PENDING_POLICY").length,
    [documents],
  );
  const indexedCount = useMemo(
    () => documents.filter((document) => document.status === "INDEXED").length,
    [documents],
  );
  const activeCount = useMemo(
    () => documents.filter((document) => document.status !== "DELETED").length,
    [documents],
  );

  async function refresh() {
    try {
      setError(null);
      const [nextDocuments, nextOptions, nextIngestion] = await Promise.all([
        listAdminDocuments(email),
        options ? Promise.resolve(options) : getPolicyOptions(email),
        getIngestionStatus(email),
      ]);

      setDocuments(nextDocuments);
      if (!options) setOptions(nextOptions);
      setIngestion(nextIngestion);

      if (selected) {
        const refreshed = await getDocumentDetail(email, selected.id);
        setSelected(refreshed);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load admin data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 2500);
    return () => window.clearInterval(timer);
    // The selected document and options are deliberately not dependencies: this is a polling loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email]);

  function openDocument(document: AdminDocument) {
    setBusy(true);
    setError(null);
    void getDocumentDetail(email, document.id)
      .then((detail) => {
        setSelected(detail);
        setScope(detail.access_scope as AccessScope);
        setClassification(detail.classification as Classification);
        setRoleIds(detail.acl.roles.map((item) => item.id));
        setDepartmentIds(detail.acl.departments.map((item) => item.id));
        setUserIds(detail.acl.users.map((item) => item.id));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Unable to load document details.");
      })
      .finally(() => setBusy(false));
  }

  async function savePolicy() {
    if (!selected) return;

    setBusy(true);
    setError(null);

    try {
      const detail = await updateDocumentPolicy(
        email,
        selected.id,
        {
          classification,
          access_scope: scope,
          department_ids: scope === "DEPARTMENT" ? departmentIds : [],
          role_ids: scope === "ROLE" ? roleIds : [],
          user_ids: scope === "USER" ? userIds : [],
        },
      );

      setSelected(detail);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Policy update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload() {
    if (!uploadFile) {
      setError("Choose a document before uploading.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const result = await uploadDocument(email, category, uploadFile);
      setUploadFile(null);
      const input = document.getElementById("admin-upload-input") as HTMLInputElement | null;
      if (input) input.value = "";
      await refresh();
      setSelected(result.document);
      setScope("PUBLIC");
      setClassification("INTERNAL");
      setRoleIds([]);
      setDepartmentIds([]);
      setUserIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    if (!window.confirm(`Delete ${selected.filename}? The file will be removed and its search index will be cleaned in the background.`)) return;

    setBusy(true);
    setError(null);
    try {
      await deleteDocument(email, selected.id);
      setSelected(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReindex() {
    if (!selected) return;

    setBusy(true);
    setError(null);
    try {
      const detail = await reindexDocument(email, selected.id);
      setSelected(detail);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-index request failed.");
    } finally {
      setBusy(false);
    }
  }

  function toggle(setter: Dispatch<SetStateAction<number[]>>, id: number) {
    setter((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : [...current, id],
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-6 py-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-400" />
            <span className="text-sm font-semibold text-white">Policy & Document Control</span>
          </div>
          <p className="mt-1 text-[11px] text-white/30">
            Approve access, upload files, inspect audit history and monitor background indexing.
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-2 text-white/30 hover:bg-white/[0.05] hover:text-white/70"
          title="Back to assistant"
        >
          <X size={16} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_440px]">
          <div className="min-h-0 overflow-y-auto p-5">
            <div className="mb-5 grid gap-3 sm:grid-cols-4">
              {[
                ["Active documents", activeCount],
                ["Pending policy", pendingCount],
                ["Indexed", indexedCount],
                ["Queue", ingestion?.queue_depth ?? 0],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <div className="text-[10px] uppercase tracking-[0.12em] text-white/20">{label}</div>
                  <div className="mt-2 text-xl font-semibold text-white/80">{value}</div>
                </div>
              ))}
            </div>

            <div className="mb-5 rounded-2xl border border-white/[0.06] bg-[#0d1014] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xs font-medium text-white/65">
                    <FileUp size={14} className="text-emerald-400" />
                    Upload document
                  </div>
                  <div className="mt-1 text-[10px] text-white/25">New uploads remain pending until an admin approves a policy.</div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-[180px_1fr_auto]">
                <select
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="rounded-xl border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-white outline-none"
                >
                  {CATEGORIES.map((item) => (
                    <option key={item} value={item} className="bg-[#111419]">
                      {item}
                    </option>
                  ))}
                </select>

                <input
                  id="admin-upload-input"
                  type="file"
                  accept=".pdf,.docx,.xlsx,.csv,.txt,.md"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                  className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-white/50 file:mr-3 file:rounded-lg file:border-0 file:bg-white/[0.08] file:px-3 file:py-1.5 file:text-[11px] file:font-medium file:text-white/70"
                />

                <button
                  onClick={() => void handleUpload()}
                  disabled={busy || !uploadFile}
                  className="rounded-xl bg-white px-4 py-2 text-xs font-semibold text-black disabled:cursor-not-allowed disabled:bg-white/[0.08] disabled:text-white/20"
                >
                  Upload
                </button>
              </div>
            </div>

            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-400/10 bg-red-400/[0.04] p-3 text-xs text-red-300/70">
                <CircleAlert size={14} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="overflow-hidden rounded-2xl border border-white/[0.06] bg-[#0d1014]">
              <div className="flex items-center justify-between border-b border-white/[0.05] px-4 py-3">
                <div className="flex items-center gap-2 text-xs font-medium text-white/60">
                  <FileArchive size={14} className="text-white/35" />
                  Document registry
                </div>
                <button
                  onClick={() => void refresh()}
                  className="rounded-lg p-1.5 text-white/25 hover:bg-white/[0.05] hover:text-white/60"
                >
                  <RefreshCw size={13} />
                </button>
              </div>

              {loading ? (
                <div className="flex items-center gap-2 p-6 text-xs text-white/30">
                  <LoaderCircle size={14} className="animate-spin" /> Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="p-6 text-xs text-white/25">No documents registered.</div>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {documents.map((document) => (
                    <button
                      key={document.id}
                      onClick={() => openDocument(document)}
                      className={`flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/[0.025] ${selected?.id === document.id ? "bg-white/[0.035]" : ""}`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-xs font-medium text-white/70">{document.title}</div>
                        <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1 text-[10px] text-white/20">
                          <span>{document.relative_path}</span>
                          <span>·</span>
                          <span>{document.owner_department.code}</span>
                          <span>·</span>
                          <span>{bytes(document.file_size)}</span>
                        </div>
                      </div>
                      <span className={`rounded-full border px-2 py-1 text-[9px] font-semibold ${statusClass(document.status)}`}>
                        {document.status}
                      </span>
                      <ChevronRight size={14} className="shrink-0 text-white/15" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <aside className="min-h-0 overflow-y-auto border-t border-white/[0.06] bg-[#0a0c0f] p-5 xl:border-l xl:border-t-0">
            {!selected ? (
              <div className="flex h-full min-h-[420px] items-center justify-center text-center">
                <div className="max-w-sm">
                  <History size={20} className="mx-auto mb-3 text-white/20" />
                  <div className="text-sm font-medium text-white/45">Select a document</div>
                  <div className="mt-2 text-[11px] leading-5 text-white/20">See filesystem metadata, policy grants, audit history and indexing state.</div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-white/80">{selected.title}</div>
                      <div className="mt-1 break-all text-[10px] text-white/25">{selected.relative_path}</div>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-1 text-[9px] font-semibold ${statusClass(selected.status)}`}>{selected.status}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {[
                    ["Type", selected.source_type],
                    ["Version", `v${selected.version}`],
                    ["Size", bytes(selected.file_size)],
                    ["Owner", selected.owner_department.code],
                    ["Classification", selected.classification],
                    ["Scope", selected.access_scope],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-2.5">
                      <div className="text-[9px] uppercase tracking-[0.12em] text-white/15">{label}</div>
                      <div className="mt-1 truncate text-[11px] text-white/55">{value}</div>
                    </div>
                  ))}
                </div>

                <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3">
                  <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/20">Ownership & audit</div>
                  <div className="space-y-2 text-[10px]">
                    <div><span className="text-white/20">Added by:</span> <span className="text-white/45">{selected.created_by?.name ?? "System / pre-existing corpus"}</span></div>
                    <div><span className="text-white/20">Policy by:</span> <span className="text-white/45">{selected.policy_updated_by?.name ?? "Not approved yet"}</span></div>
                    <div><span className="text-white/20">Policy time:</span> <span className="text-white/45">{date(selected.policy_updated_at)}</span></div>
                    <div><span className="text-white/20">Indexed:</span> <span className="text-white/45">{date(selected.indexed_at)}</span></div>
                  </div>
                </div>

                <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3">
                  <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/20">Filesystem</div>
                  <div className="space-y-2 text-[10px]">
                    <div><span className="text-white/20">Exists:</span> <span className={selected.filesystem.exists ? "text-emerald-300/70" : "text-red-300/70"}>{selected.filesystem.exists ? "Yes" : "No"}</span></div>
                    <div className="break-all"><span className="text-white/20">Path:</span> <span className="text-white/40">{selected.filesystem.path ?? "—"}</span></div>
                    <div className="break-all"><span className="text-white/20">SHA-256:</span> <span className="font-mono text-white/25">{selected.checksum}</span></div>
                  </div>
                </div>

                <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/20">Policy</div>
                    <span className="text-[9px] text-white/20">Current + approve</span>
                  </div>

                  <div className="space-y-2">
                    <select value={classification} onChange={(event) => setClassification(event.target.value as Classification)} className="w-full rounded-lg border border-white/[0.07] bg-[#111419] px-2.5 py-2 text-[11px] text-white/65">
                      {CLASSIFICATIONS.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                    <select value={scope} onChange={(event) => setScope(event.target.value as AccessScope)} className="w-full rounded-lg border border-white/[0.07] bg-[#111419] px-2.5 py-2 text-[11px] text-white/65">
                      {SCOPES.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>

                    {scope === "ROLE" && options && (
                      <div className="space-y-1.5">
                        {options.roles.map((role) => (
                          <label key={role.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.025]">
                            <input type="checkbox" checked={roleIds.includes(role.id)} onChange={() => toggle(setRoleIds, role.id)} />
                            <span className="text-[10px] text-white/45">{role.code}</span>
                          </label>
                        ))}
                      </div>
                    )}

                    {scope === "DEPARTMENT" && options && (
                      <div className="space-y-1.5">
                        {options.departments.map((department) => (
                          <label key={department.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-white/[0.025]">
                            <input type="checkbox" checked={departmentIds.includes(department.id)} onChange={() => toggle(setDepartmentIds, department.id)} />
                            <span className="text-[10px] text-white/45">{department.code} · {department.name}</span>
                          </label>
                        ))}
                      </div>
                    )}

                    {scope === "USER" && options && (
                      <select multiple value={userIds.map(String)} onChange={(event) => {
                        const target = event.target as HTMLSelectElement;
                        setUserIds(
                          Array.from(
                            target.selectedOptions,
                            (option: HTMLOptionElement) => Number(option.value),
                          ),
                        );
                      }} className="min-h-32 w-full rounded-lg border border-white/[0.07] bg-[#111419] px-2.5 py-2 text-[10px] text-white/60">
                        {options.users.map((user) => (
                          <option key={user.id} value={user.id}>{user.name} · {user.role}</option>
                        ))}
                      </select>
                    )}

                    <button onClick={() => void savePolicy()} disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-400 px-3 py-2 text-[11px] font-semibold text-black disabled:cursor-not-allowed disabled:opacity-50">
                      {busy ? <LoaderCircle size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                      Approve policy & queue indexing
                    </button>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button onClick={() => void handleReindex()} disabled={busy || selected.status === "DELETED"} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-2 text-[10px] text-white/45 hover:bg-white/[0.05] disabled:opacity-40">
                    <RefreshCw size={12} /> Re-index
                  </button>
                  <button onClick={() => void handleDelete()} disabled={busy || selected.status === "DELETED"} className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-red-400/10 bg-red-400/[0.04] px-3 py-2 text-[10px] text-red-300/70 hover:bg-red-400/[0.07] disabled:opacity-40">
                    <Trash2 size={12} /> Delete file
                  </button>
                </div>

                <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3">
                  <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/20">Audit trail</div>
                  <div className="space-y-3">
                    {selected.audit_logs.length === 0 ? (
                      <div className="text-[10px] text-white/20">No audit events recorded.</div>
                    ) : selected.audit_logs.map((log) => (
                      <div key={log.id} className="border-l border-white/[0.07] pl-3">
                        <div className="text-[10px] font-medium text-white/50">{log.action}</div>
                        <div className="mt-0.5 text-[9px] text-white/20">{log.actor?.name ?? "System"} · {date(log.created_at)}</div>
                        <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap break-words text-[9px] leading-4 text-white/20">{JSON.stringify(log.details, null, 2)}</pre>
                      </div>
                    ))}
                  </div>
                </div>

                {ingestion && (
                  <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-3 text-[10px] text-white/25">
                    Background worker: <span className={ingestion.running ? "text-emerald-300/70" : "text-amber-300/70"}>{ingestion.running ? "online" : "stopped"}</span>
                    {ingestion.active_job ? ` · ${ingestion.active_job.action} #${ingestion.active_job.document_id}` : ""}
                    {ingestion.last_error ? <div className="mt-1 text-red-300/60">{ingestion.last_error}</div> : null}
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
