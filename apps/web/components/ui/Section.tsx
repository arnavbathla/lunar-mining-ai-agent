import { ReactNode } from "react";
import { cx } from "@/lib/utils";

interface SectionProps {
  step: number;
  title: string;
  description?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Section({
  step,
  title,
  description,
  right,
  children,
  className,
}: SectionProps) {
  return (
    <section className={cx("flex flex-col gap-3", className)}>
      <header className="flex items-end justify-between gap-3 border-b border-line pb-2">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] tracking-widest text-muted">
            {String(step).padStart(2, "0")}
          </span>
          <div>
            <h2 className="text-base font-semibold tracking-tight text-ink">
              {title}
            </h2>
            {description ? (
              <p className="text-[12px] text-muted mt-0.5">{description}</p>
            ) : null}
          </div>
        </div>
        {right ? <div>{right}</div> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}
