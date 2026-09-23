import {
  Fingerprint,
  LockKeyhole,
  Shield,
} from "lucide-react";

import {
  demoUsers,
  roleDescriptions,
} from "../data/demoUsers";

import type { DemoUser } from "../types";

interface AccessPanelProps {
  selectedRole: string;
  selectedUser: DemoUser;
  onRoleChange: (role: string) => void;
}

export function AccessPanel({
  selectedRole,
  selectedUser,
  onRoleChange,
}: AccessPanelProps) {
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#0d1014] p-4 shadow-2xl shadow-black/20">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-400/10">
              <Shield
                size={14}
                className="text-emerald-400"
              />
            </div>

            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-white/70">
              Demo Identity
            </span>
          </div>

          <p className="mt-2 text-[11px] leading-5 text-white/30">
            Switch roles to demonstrate
            permission-aware retrieval.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {/* Role selector */}
        <div>
          <label className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.12em] text-white/25">
            Role
          </label>

          <div className="relative">
            <select
              value={selectedRole}
              onChange={(event) =>
                onRoleChange(event.target.value)
              }
              className="w-full appearance-none rounded-xl border border-white/[0.08] bg-white/[0.025] px-3 py-2.5 pr-9 text-xs text-white outline-none transition focus:border-emerald-400/30 focus:bg-white/[0.04]"
            >
              {Array.from(
                new Set(
                  demoUsers.map(
                    (user) => user.role
                  )
                )
              ).map((role) => (
                <option
                  key={role}
                  value={role}
                  className="bg-[#111419] text-white"
                >
                  {role}
                </option>
              ))}
            </select>

            <svg
              className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/30"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </div>
        </div>

        {/* Fixed user identity */}
        <div>
          <label className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.12em] text-white/25">
            User
          </label>

          <div className="flex items-center gap-3 rounded-xl border border-emerald-400/20 bg-white/[0.025] px-3 py-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.06] text-[10px] font-semibold text-white/65">
              {selectedUser.accent}
            </div>

            <div className="min-w-0">
              <div className="truncate text-xs font-medium text-white/80">
                {selectedUser.name}
              </div>

              <div className="mt-0.5 truncate text-[10px] text-white/25">
                {selectedUser.email}
              </div>
            </div>
          </div>
        </div>

        {/* Authorization scope */}
        <div className="rounded-xl border border-emerald-400/[0.08] bg-emerald-400/[0.035] p-3">
          <div className="flex items-start gap-2.5">
            <LockKeyhole
              size={14}
              className="mt-0.5 shrink-0 text-emerald-400/80"
            />

            <div className="min-w-0">
              <div className="text-[11px] font-medium text-emerald-300/80">
                Authorization Scope
              </div>

              <div className="mt-1 text-[11px] leading-5 text-white/35">
                {roleDescriptions[
                  selectedRole
                ] ??
                  roleDescriptions[
                    selectedUser.role
                  ] ??
                  "Access controlled by the SecureRAG policy engine."}
              </div>
            </div>
          </div>
        </div>

        {/* Identity */}
        <div className="flex items-center gap-2 border-t border-white/[0.05] pt-3">
          <Fingerprint
            size={12}
            className="text-white/20"
          />

          <span className="truncate text-[10px] text-white/25">
            {selectedUser.email}
          </span>
        </div>
      </div>
    </section>
  );
}