/** 提示组件，用于解释术语与指标。 */
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as React from "react";

import { cn } from "../../lib/utils";

/** 提示容器。 */
const TooltipProvider = TooltipPrimitive.Provider;
/** 提示根组件。 */
const Tooltip = TooltipPrimitive.Root;
/** 触发器。 */
const TooltipTrigger = TooltipPrimitive.Trigger;

/** 提示内容。 */
const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-lg border border-white/15 bg-terminal-900 px-3 py-1.5 text-xs text-white shadow-glass animate-in fade-in-50",
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };

