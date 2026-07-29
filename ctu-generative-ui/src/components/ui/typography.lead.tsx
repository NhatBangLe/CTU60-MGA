import { cn } from "@/lib/utils";
import { ComponentProps } from "react";

export default function TypographyLead({
  children,
  className,
  ...props
}: ComponentProps<"p">) {
  return (
    <p
      className={cn("text-muted-foreground dark:text-muted text-xl", className)}
      {...props}
    >
      {children}
    </p>
  );
}
