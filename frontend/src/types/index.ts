export interface ChatRequest {
  query: string;
  top_k?: number;
}

export interface Citation {
  source_id: string;
  citation: string;
  document_id: number | null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  retrieval_count: number;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface DemoUser {
  id: number;
  name: string;
  email: string;
  role: string;
  department: string;
  accent: string;
  description: string;
}

export interface RoleGroup {
  role: string;
  department: string;
  users: DemoUser[];
}

export type AccessScope =
  | "PUBLIC"
  | "DEPARTMENT"
  | "ROLE"
  | "USER";

export type Classification =
  | "PUBLIC"
  | "PUBLIC_INTERNAL"
  | "INTERNAL"
  | "CONFIDENTIAL"
  | "RESTRICTED";

export interface IdentitySummary {
  id: number;
  email: string;
  name: string;
  role: string;
  department: string;
}

export interface AdminDocument {
  id: number;
  document_key: string;
  title: string;
  filename: string;
  relative_path: string;
  source_type: string;
  classification: string;
  access_scope: string;
  status: string;
  version: number;
  file_size: number;
  checksum: string;
  created_at: string;
  updated_at: string;
  indexed_at: string | null;
  last_seen_at: string | null;
  created_by: IdentitySummary | null;
  policy_updated_by: IdentitySummary | null;
  policy_updated_at: string | null;
  deleted_by: IdentitySummary | null;
  deleted_at: string | null;
  owner_department: {
    id: number;
    code: string;
    name: string;
  };
}

export interface DocumentDetail extends AdminDocument {
  acl: {
    roles: Array<{ id: number; code: string; name: string }>;
    departments: Array<{ id: number; code: string; name: string }>;
    users: Array<{
      id: number;
      employee_code: string;
      name: string;
      email: string;
      role: string;
      department: string;
    }>;
  };
  audit_logs: Array<{
    id: number;
    action: string;
    actor: IdentitySummary | null;
    details: Record<string, unknown>;
    created_at: string;
  }>;
  filesystem: {
    path: string | null;
    relative_path: string;
    exists: boolean;
    size_bytes: number;
  };
}

export interface PolicyOptions {
  roles: Array<{
    id: number;
    code: string;
    name: string;
    is_global_access: boolean;
  }>;
  departments: Array<{
    id: number;
    code: string;
    name: string;
  }>;
  users: Array<{
    id: number;
    employee_code: string;
    name: string;
    email: string;
    role: string;
    department: string;
  }>;
}

export interface IngestionStatus {
  running: boolean;
  queue_depth: number;
  active_job: {
    action: string;
    document_id: number;
  } | null;
  last_error: string | null;
  last_finished_at: number | null;
}
