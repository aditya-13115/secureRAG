import {
  Activity,
  Command,
  ShieldCheck,
} from "lucide-react";
import type { DemoUser } from "../types";

interface TopBarProps {
  user: DemoUser;
}

export function TopBar({
  user,
}: TopBarProps) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-white/[0.06] bg-[#090b0e]/80 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.05]">
          <ShieldCheck
            size={18}
            className="text-emerald-400"
          />
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-wide text-white">
              MONK-E
            </span>

            <span className="text-white/20">
              /
            </span>

            <span className="text-sm font-medium text-white/60">
              SecureRAG
            </span>
          </div>

          <div className="text-[11px] text-white/30">
            Internal knowledge intelligence
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-lg border border-emerald-400/10 bg-emerald-400/[0.05] px-3 py-2 md:flex">
          <Activity
            size={13}
            className="text-emerald-400"
          />
          <span className="text-[11px] text-emerald-300/80">
            RAG ONLINE
          </span>
        </div>

        <div className="hidden items-center gap-2 text-white/25 lg:flex">
          <Command size={13} />
          <span className="text-[11px]">
            Enterprise workspace
          </span>
        </div>

        <div className="flex items-center gap-2 border-l border-white/[0.06] pl-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-[11px] font-semibold text-white/70">
            {user.accent}
          </div>

          <div className="hidden sm:block">
            <div className="text-xs font-medium text-white/80">
              {user.name}
            </div>
            <div className="text-[10px] text-white/30">
              {user.role}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}