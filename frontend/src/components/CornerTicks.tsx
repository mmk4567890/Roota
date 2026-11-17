import type { ReactNode } from "react";

interface CornerTicksProps {
  children: ReactNode;
  className?: string;
}

/** Viewfinder L-corners around the current-check / outcome panel only. */
export function CornerTicks({ children, className = "" }: CornerTicksProps) {
  return (
    <div className={`corner-frame ${className}`.trim()}>
      {children}
      <span className="corner-br" aria-hidden="true" />
    </div>
  );
}
