"use client";

import { cn } from "@/lib/utils";
import React from "react";
import TypographyH1 from "./ui/typography.h1";
import { useTranslations } from "next-intl";
import Image from "next/image";
import LocaleSwitcher from "./locale-switcher";
import { Button } from "./ui/button";
import { useRouter } from "@/i18n/navigation";
import { House, Users } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

const Header = ({ className, ...props }: React.ComponentProps<"header">) => {
  const orgTrans = useTranslations("Organization");
  const appTrans = useTranslations("App");
  const router = useRouter();

  return (
    <header
      className={cn(
        "w-full h-16 p-3 flex flex-row items-center justify-between bg-primary",
        className,
      )}
      {...props}
    >
      <div className="flex flex-row gap-5 items-center">
        <a
          target="_blank"
          href="https://www.ctu.edu.vn"
          className="flex flex-row gap-2 items-center cursor-pointer"
        >
          <Image
            src={"/app_logo.png"}
            width={50}
            height={50}
            alt={appTrans("altLogo")}
          />
          <TypographyH1 className="hidden md:block text-secondary">
            {orgTrans("name")}
          </TypographyH1>
        </a>

        <div className="flex flex-row gap-3 items-center">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                className="cursor-pointer bg-white text-black hover:bg-white transition duration-300 ease-in-out hover:-translate-y-1 hover:scale-105"
                variant={"default"}
                onClick={() => router.replace("/")}
              >
                <House />
                <span className="hidden md:inline-block">
                  {appTrans("home")}
                </span>
              </Button>
            </TooltipTrigger>
            <TooltipContent className="md:hidden">
              <span>{appTrans("home")}</span>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                className="cursor-pointer bg-white text-black hover:bg-white transition duration-300 ease-in-out hover:-translate-y-1 hover:scale-105"
                variant={"default"}
                onClick={() => router.replace("/about")}
              >
                <Users />
                <span className="hidden md:inline-block">
                  {appTrans("about")}
                </span>
              </Button>
            </TooltipTrigger>
            <TooltipContent className="md:hidden">
              <span>{appTrans("about")}</span>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>

      <div>
        <LocaleSwitcher />
      </div>
    </header>
  );
};

export default Header;
