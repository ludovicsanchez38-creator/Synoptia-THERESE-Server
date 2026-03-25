import { useToastStore } from "../../stores/toastStore";
import type { ToastType } from "../../stores/toastStore";
import { X } from "lucide-react";

const typeStyles: Record<ToastType, string> = {
  success: "bg-emerald-900/90 border-emerald-500 text-emerald-100",
  error: "bg-red-900/90 border-red-500 text-red-100",
  warning: "bg-amber-900/90 border-amber-500 text-amber-100",
  info: "bg-blue-900/90 border-blue-500 text-blue-100",
};

const typeIcons: Record<ToastType, string> = {
  success: "\u2713",
  error: "\u2715",
  warning: "\u26A0",
  info: "\u2139",
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm" role="log" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg backdrop-blur-sm animate-slide-in ${typeStyles[toast.type]}`}
          role={toast.type === "error" ? "alert" : "status"}
        >
          <span className="text-lg shrink-0">{typeIcons[toast.type]}</span>
          <p className="text-sm flex-1">{toast.message}</p>
          <button
            onClick={() => removeToast(toast.id)}
            className="shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
            aria-label="Fermer la notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
