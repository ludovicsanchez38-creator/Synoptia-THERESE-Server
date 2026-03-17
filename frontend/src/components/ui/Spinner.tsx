interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeMap = {
  sm: "h-4 w-4 border-2",
  md: "h-8 w-8 border-2",
  lg: "h-12 w-12 border-3",
};

export default function Spinner({ size = "md", className = "" }: SpinnerProps) {
  return (
    <div
      className={`${sizeMap[size]} rounded-full border-[var(--color-muted)]/30 border-t-[var(--color-cyan)] animate-spin ${className}`}
      role="status"
      aria-label="Chargement"
    />
  );
}
