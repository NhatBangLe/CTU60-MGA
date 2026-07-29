import { cn } from "@/lib/utils";
import { ComponentProps } from "react";

export default function TypographyH1({
  children,
  className,
  ...props
}: ComponentProps<"h1">) {
  return (
    <h1
      className={cn(
        "scroll-m-20 text-center text-4xl font-extrabold tracking-tight text-balance",
        className
      )}
      {...props}
    >
      {children}
    </h1>
  );
}
