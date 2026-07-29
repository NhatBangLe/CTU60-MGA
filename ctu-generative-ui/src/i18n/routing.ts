import { defineRouting } from "next-intl/routing";

export const locales = ["vi", "en"];

export const defaultLocale = "vi";

export const routing = defineRouting({
  locales, // A list of all locales that are supported
  defaultLocale, // Used when no locale matches
  localeDetection: false,
});
