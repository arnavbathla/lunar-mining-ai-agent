import { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary:
    "bg-ink text-paper border border-ink hover:bg-black disabled:opacity-50",
  secondary:
    "bg-paper text-ink border border-line hover:border-ink disabled:opacity-50",
  ghost: "bg-transparent text-ink border border-transparent hover:bg-bone",
  danger:
    "bg-paper text-status-fail border border-status-fail hover:bg-red-50 disabled:opacity-50",
};

const sizeClass: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[12px]",
  md: "px-4 py-2 text-[13px]",
};

export function Button({
  children,
  variant = "secondary",
  size = "md",
  loading,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center gap-2 rounded-md font-medium tracking-tight",
        "transition-colors duration-100 disabled:cursor-not-allowed",
        variantClass[variant],
        sizeClass[size],
        className,
      )}
    >
      {loading ? (
        <span
          aria-hidden
          className="h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin"
        />
      ) : null}
      {children}
    </button>
  );
}
