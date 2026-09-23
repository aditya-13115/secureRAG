import type {
  FormEvent,
  KeyboardEvent,
} from "react";

import {
  ArrowUp,
  LoaderCircle,
} from "lucide-react";

interface ChatComposerProps {
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function ChatComposer({
  value,
  disabled,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    if (!disabled) {
      onSubmit();
    }
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      if (!disabled) {
        onSubmit();
      }
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-white/[0.08] bg-[#0c0f13] p-2 shadow-2xl shadow-black/25"
    >
      <textarea
        value={value}
        disabled={disabled}
        onChange={(event) =>
          onChange(event.target.value)
        }
        onKeyDown={handleKeyDown}
        placeholder="Ask about your authorized company knowledge..."
        rows={3}
        className="w-full resize-none bg-transparent px-3 py-2 text-sm leading-6 text-white/80 outline-none placeholder:text-white/20 disabled:cursor-not-allowed disabled:opacity-50"
      />

      <div className="flex items-center justify-between border-t border-white/[0.05] px-2 pt-2">
        <div className="text-[10px] text-white/20">
          Shift + Enter for a new line
        </div>

        <button
          type="submit"
          disabled={
            disabled || !value.trim()
          }
          className="flex h-9 items-center gap-2 rounded-xl bg-white px-3.5 text-xs font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:bg-white/[0.08] disabled:text-white/20"
        >
          {disabled ? (
            <>
              <LoaderCircle
                size={14}
                className="animate-spin"
              />
              Thinking
            </>
          ) : (
            <>
              Ask
              <ArrowUp size={14} />
            </>
          )}
        </button>
      </div>
    </form>
  );
}