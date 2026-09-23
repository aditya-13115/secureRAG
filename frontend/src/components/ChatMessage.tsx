import {
  Bot,
  UserRound,
} from "lucide-react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
}

function renderInline(
  content: string
) {
  const parts = content.split(
    /(\*\*[^*]+\*\*|\[S\d+\])/g
  );

  return parts.map(
    (part, index) => {
      if (
        /^\*\*[^*]+\*\*$/.test(part)
      ) {
        return (
          <strong
            key={index}
            className="font-semibold text-white"
          >
            {part.slice(2, -2)}
          </strong>
        );
      }

      if (/^\[S\d+\]$/.test(part)) {
        return (
          <span
            key={index}
            className="mx-0.5 rounded-md border border-emerald-400/10 bg-emerald-400/[0.07] px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300"
          >
            {part}
          </span>
        );
      }

      return (
        <span key={index}>
          {part}
        </span>
      );
    }
  );
}

export function ChatMessage({
  role,
  content,
}: ChatMessageProps) {
  const isUser =
    role === "user";

  return (
    <div
      className={`flex gap-3 ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-emerald-400/10 bg-emerald-400/[0.06]">
          <Bot
            size={15}
            className="text-emerald-400"
          />
        </div>
      )}

      <div
        className={`max-w-[820px] ${
          isUser
            ? "rounded-2xl rounded-tr-md border border-white/[0.08] bg-white/[0.055] px-4 py-3"
            : "pt-1"
        }`}
      >
        <div className="whitespace-pre-wrap text-sm leading-7 text-white/75">
          {renderInline(content)}
        </div>
      </div>

      {isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04]">
          <UserRound
            size={14}
            className="text-white/50"
          />
        </div>
      )}
    </div>
  );
}