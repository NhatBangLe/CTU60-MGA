"use client";

import { usePathname, useRouter } from "@/i18n/navigation";
import { locales } from "@/i18n/routing";
import { useParams } from "next/navigation";
import { useTransition } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { useLocale, useTranslations } from "next-intl";

const LocaleSwitcher = () => {
  const appTrans = useTranslations("App");
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const pathname = usePathname();
  const params = useParams();
  const locale = useLocale();

  function onSelectChange(nextLocale: string) {
    startTransition(() => {
      router.replace(
        // @ts-expect-error -- TypeScript will validate that only known `params`
        // are used in combination with a given `pathname`. Since the two will
        // always match for the current route, we can skip runtime checks.
        { pathname, params },
        { locale: nextLocale },
      );
    });
  }

  return (
    <Select disabled={isPending} onValueChange={onSelectChange} value={locale}>
      <SelectTrigger className="w-16 md:w-[140px] font-bold bg-white">
        <SelectValue placeholder={appTrans("language")} />
      </SelectTrigger>
      <SelectContent>
        {locales.map((curr) => {
          return (
            <SelectItem key={curr} value={curr}>
              {appTrans("locale", { locale: curr })}
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
};

export default LocaleSwitcher;
