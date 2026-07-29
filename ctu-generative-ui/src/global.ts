import { routing } from "@/i18n/routing";
import { formats } from "@/i18n/request";
import messages from "./messages/vi.json";

export type SupportedLocale = (typeof routing.locales)[number];

declare module "next-intl" {
  interface AppConfig {
    Locale: SupportedLocale;
    Messages: typeof messages;
    Formats: typeof formats;
  }
}
