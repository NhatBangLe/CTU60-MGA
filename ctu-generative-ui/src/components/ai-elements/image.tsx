/* eslint-disable @next/next/no-img-element */
import { cn } from "@/lib/utils";

export type ImageProps = {
  className?: string;
  alt?: string;
  url: string;
};

export const Image = ({ url, ...props }: ImageProps) => (
  <img
    {...props}
    alt={props.alt}
    className={cn(
      "h-auto max-w-full overflow-hidden rounded-md",
      props.className
    )}
    src={url}
    crossOrigin="anonymous"
  />
);
