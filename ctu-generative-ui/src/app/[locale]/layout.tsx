import Header from "@/components/header";
import { routing } from "@/i18n/routing";
import { hasLocale, Locale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { K2D } from "next/font/google";
import "./style.css";
import { Toaster } from "@/components/ui/sonner";
import { AppVersion } from "@/lib/constants";

const k2d = K2D({
  weight: ["100", "200", "300", "400", "500", "600", "700", "800"],
  subsets: ["latin", "vietnamese"],
});

// const readexPro = Readex_Pro({
//   subsets: ["latin", "vietnamese"],
// });

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata(
  props: Omit<LayoutProps<"/[locale]">, "children">,
) {
  const { locale } = await props.params;

  const t = await getTranslations({
    locale: locale as Locale,
    namespace: "App",
  });

  return {
    title: t("name"),
    description: t("description", { version: AppVersion }),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<LayoutProps<"/[locale]">>) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();

  // Enable static rendering
  setRequestLocale(locale);

  return (
    <html lang={locale}>
      <body className={`${k2d.className} relative antialiased`}>
        <main className="w-full h-full">
          <NextIntlClientProvider locale={locale}>
            <Header className="z-50 fixed" />
            {children}
            <Toaster
              closeButton
              duration={5000}
              position="top-right"
              theme="system"
            />
          </NextIntlClientProvider>
        </main>
      </body>
    </html>
  );
}
