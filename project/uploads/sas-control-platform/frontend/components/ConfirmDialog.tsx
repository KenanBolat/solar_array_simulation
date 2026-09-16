"use client";

import { useState } from "react";
import { TriangleAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Hazardous-action confirmation. For high-consequence actions the caller can
 * require the operator to type a confirmation phrase (a lightweight dual
 * confirmation) before the confirm button enables.
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  destructive,
  requirePhrase,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
  requirePhrase?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  if (!open) return null;
  const ready = !requirePhrase || typed.trim().toUpperCase() === requirePhrase.toUpperCase();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="panel w-full max-w-md">
        <div className="panel-header">
          <div className="flex items-center gap-2">
            <TriangleAlert
              size={16}
              style={{ color: destructive ? "var(--color-alarm)" : "var(--color-warning)" }}
            />
            <span className="text-sm font-semibold">{title}</span>
          </div>
          <button onClick={onCancel} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
            <X size={16} />
          </button>
        </div>
        <div className="space-y-3 p-4 text-sm text-[var(--color-ink-dim)]">
          <div>{body}</div>
          {requirePhrase ? (
            <div className="space-y-1.5">
              <p className="text-xs text-[var(--color-ink-faint)]">
                Type <span className="readout text-[var(--color-ink)]">{requirePhrase}</span> to
                confirm.
              </p>
              <input
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                autoFocus
                className="readout h-9 w-full rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)] focus-visible:border-[var(--color-active)]"
              />
            </div>
          ) : null}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              variant={destructive ? "danger" : "warning"}
              disabled={!ready}
              onClick={() => {
                setTyped("");
                onConfirm();
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
