import type {
  AdminDocument,
  ChatRequest,
  ChatResponse,
  DocumentDetail,
  IngestionStatus,
  PolicyOptions,
} from "../types";

const API_URL =
  import.meta.env.VITE_API_URL ??
  "http://127.0.0.1:8000";

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") {
      return data.detail;
    }
  } catch {
    // Fall through to a generic message.
  }

  return `Request failed with HTTP ${response.status}.`;
}

async function requestJson<T>(
  email: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      "X-User-Email": email,
    },
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<T>;
}

export async function sendChatMessage(
  email: string,
  request: ChatRequest,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(
    email,
    "/api/chat",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    },
  );
}

export async function listAdminDocuments(
  email: string,
  status?: string,
): Promise<AdminDocument[]> {
  const query = status
    ? `?status=${encodeURIComponent(status)}`
    : "";

  return requestJson<AdminDocument[]>(
    email,
    `/api/documents${query}`,
  );
}

export async function getPolicyOptions(
  email: string,
): Promise<PolicyOptions> {
  return requestJson<PolicyOptions>(
    email,
    "/api/documents/policy-options",
  );
}

export async function getDocumentDetail(
  email: string,
  documentId: number,
): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(
    email,
    `/api/documents/${documentId}`,
  );
}

export interface PolicyPayload {
  classification: string;
  access_scope: string;
  department_ids: number[];
  role_ids: number[];
  user_ids: number[];
}

export async function updateDocumentPolicy(
  email: string,
  documentId: number,
  payload: PolicyPayload,
): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(
    email,
    `/api/documents/${documentId}/policy`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function uploadDocument(
  email: string,
  category: string,
  file: File,
): Promise<{ document: DocumentDetail; ingestion_queued: boolean }> {
  const form = new FormData();
  form.append("category", category);
  form.append("file", file);

  return requestJson<{ document: DocumentDetail; ingestion_queued: boolean }>(
    email,
    "/api/documents/upload",
    {
      method: "POST",
      body: form,
    },
  );
}

export async function deleteDocument(
  email: string,
  documentId: number,
): Promise<{
  document_id: number;
  status: string;
  file_removed: boolean;
  index_cleanup_queued: boolean;
}> {
  return requestJson(
    email,
    `/api/documents/${documentId}`,
    { method: "DELETE" },
  );
}

export async function reindexDocument(
  email: string,
  documentId: number,
): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(
    email,
    `/api/documents/${documentId}/reindex`,
    { method: "POST" },
  );
}

export async function getIngestionStatus(
  email: string,
): Promise<IngestionStatus> {
  return requestJson<IngestionStatus>(
    email,
    "/api/documents/ingestion/status",
  );
}
