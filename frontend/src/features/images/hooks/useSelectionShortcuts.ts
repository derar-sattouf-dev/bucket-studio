import { useEffect } from "react";

interface ShortcutHandlers {
    /** False while a dialog or drawer is open. */
    enabled: boolean;
    onToggleAll: () => void;
    onProcess?: () => void;
    onClear: () => void;
}

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/**
 * A = select all, P = process selection, Esc = deselect (ignored while typing or with
 * modifier keys). Publishing deliberately has no single-key shortcut.
 */
export function useSelectionShortcuts({ enabled, onToggleAll, onProcess, onClear }: ShortcutHandlers) {
    useEffect(() => {
        if (!enabled) return;
        function onKeyDown(event: KeyboardEvent) {
            const target = event.target as HTMLElement | null;
            if (target && (TYPING_TAGS.has(target.tagName) || target.isContentEditable)) return;
            if (event.metaKey || event.ctrlKey || event.altKey) return;

            const key = event.key.toLowerCase();
            if (key === "a") {
                event.preventDefault();
                onToggleAll();
            } else if (key === "p" && onProcess) {
                event.preventDefault();
                onProcess();
            } else if (event.key === "Escape") {
                onClear();
            }
        }
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [enabled, onToggleAll, onProcess, onClear]);
}
