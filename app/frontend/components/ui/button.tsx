// shadcn/ui-style owned component, Radix Slot + class-variance-authority (MIT).
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
const variants = cva("btn", {
  variants: {
    variant: { default: "primary", secondary: "secondary", outline: "outline" },
  },
  defaultVariants: { variant: "default" },
});
export function Button({
  className = "",
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof variants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp className={`${variants({ variant })} ${className}`} {...props} />
  );
}
