/** 通用按钮组件，统一前端交互外观。 */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "app-button",
  {
    variants: {
      variant: {
        default: "app-button-default",
        secondary: "app-button-secondary",
        ghost: "app-button-ghost",
        destructive: "app-button-destructive",
      },
      size: {
        default: "app-button-size-default",
        sm: "app-button-size-sm",
        lg: "app-button-size-lg",
        icon: "app-button-size-icon",
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
