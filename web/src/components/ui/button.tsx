/** 通用按钮组件，统一前端交互外观。 */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-terminal-300 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "border border-white/10 bg-[linear-gradient(135deg,rgba(170,230,225,0.96),rgba(128,190,240,0.92))] text-slate-950 shadow-[0_20px_48px_rgba(11,18,32,0.32),inset_0_1px_0_rgba(255,255,255,0.48)] hover:-translate-y-0.5 hover:brightness-105",
        secondary:
          "border border-white/14 bg-white/[0.07] text-white/92 shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] hover:-translate-y-0.5 hover:bg-white/[0.12]",
        ghost: "bg-transparent text-white/80 hover:bg-white/10 hover:text-white",
        destructive:
          "border border-red-300/20 bg-[linear-gradient(135deg,rgba(164,44,34,0.92),rgba(127,26,26,0.94))] text-white shadow-[0_18px_38px_rgba(83,18,18,0.24),inset_0_1px_0_rgba(255,255,255,0.12)] hover:-translate-y-0.5 hover:brightness-105",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-2xl px-6",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

/** 渲染不同变体的按钮。 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
