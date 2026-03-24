"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Key, CheckCircle2, XCircle } from "lucide-react";
import { fetchKeyStatus, setApiKeys, type KeyStatus } from "@/lib/api";

const PROVIDERS = [
  { id: "openai" as const, label: "OpenAI", placeholder: "sk-proj-..." },
  { id: "anthropic" as const, label: "Anthropic", placeholder: "sk-ant-..." },
  { id: "google" as const, label: "Google (Gemini)", placeholder: "AIzaSy..." },
];

function StatusDot({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckCircle2 className="size-3.5 text-emerald-500" />
  ) : (
    <XCircle className="size-3.5 text-zinc-600" />
  );
}

export function ApiKeyPanel() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<KeyStatus | null>(null);
  const [inputs, setInputs] = useState({ openai: "", anthropic: "", google: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchKeyStatus();
      setStatus(s);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, string> = {};
      for (const p of PROVIDERS) {
        const v = inputs[p.id].trim();
        if (v) payload[p.id] = v;
      }
      if (Object.keys(payload).length === 0) {
        setError("Enter at least one API key");
        setSaving(false);
        return;
      }
      const newStatus = await setApiKeys(payload);
      setStatus(newStatus);
      setInputs({ openai: "", anthropic: "", google: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save keys");
    } finally {
      setSaving(false);
    }
  };

  const configuredCount = status
    ? [status.openai, status.anthropic, status.google].filter(Boolean).length
    : 0;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Key className="size-4 text-zinc-500" />
          <span className="text-sm font-medium text-zinc-300">API Keys</span>
          {status && (
            <span className="ml-1 rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] tabular-nums text-zinc-500">
              {configuredCount}/3 configured
            </span>
          )}
          {status && (
            <div className="ml-2 flex items-center gap-1.5">
              {PROVIDERS.map((p) => (
                <StatusDot key={p.id} ok={status[p.id]} />
              ))}
            </div>
          )}
        </div>
        {open ? (
          <ChevronDown className="size-4 text-zinc-500" />
        ) : (
          <ChevronRight className="size-4 text-zinc-500" />
        )}
      </button>

      {open && (
        <div className="border-t border-zinc-800 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {PROVIDERS.map((p) => (
              <div key={p.id}>
                <label
                  htmlFor={`key-${p.id}`}
                  className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400"
                >
                  <StatusDot ok={status?.[p.id] ?? false} />
                  {p.label}
                </label>
                <input
                  id={`key-${p.id}`}
                  type="password"
                  value={inputs[p.id]}
                  onChange={(e) =>
                    setInputs((prev) => ({ ...prev, [p.id]: e.target.value }))
                  }
                  placeholder={status?.[p.id] ? "••• configured •••" : p.placeholder}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-600"
                />
              </div>
            ))}
          </div>

          {error && (
            <p className="mt-2 text-xs text-red-400">{error}</p>
          )}

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Keys"}
            </button>
            <p className="text-[10px] text-zinc-600">
              Keys are stored in server memory only — not written to disk
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
