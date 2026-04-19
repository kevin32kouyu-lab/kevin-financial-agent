/** 进度条组件，用于任务状态展示。 */
import * as React from "react";

import { cn } from "../../lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
}

/** 渲染百分比进度。 */
export function Progress({ value = 0, className, ...props }: ProgressProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn("relative h-2 w-full overflow-hidden rounded-full bg-white/10", className)}
      {...props}
    >
      <div
        className="h-full rounded-full bg-gradient-to-r from-terminal-400 to-terminal-300 transition-all duration-300"
        style={{ width: `${safeValue}%` }}
      />
    </div>
  );
}

