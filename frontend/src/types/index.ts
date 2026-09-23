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