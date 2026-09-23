import {
  FileText,
  ExternalLink,
} from "lucide-react";
import type { Citation } from "../types";

interface SourceCardProps {
  citation: Citation;
}

export function SourceCard({
  citation,
}: SourceCardProps) {
  return (
    <div className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 transition hover:border-white/[0.1] hover:bg-white/[0.035]">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.05]">
        <FileText
          size={14}
          className="text-white/40"
        />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-[11px] font-medium text-white/65">
          {citation.citation}
        </div>

        <div className="mt-0.5 text-[10px] text-white/20">
          {citation.source_id}
          {citation.document_id !== null
            ? ` · Document ${citation.document_id}`
            : ""}
        </div>
      </div>

      <ExternalLink
        size={12}
        className="shrink-0 text-white/15 transition group-hover:text-white/35"
      />
    </div>
  );
}