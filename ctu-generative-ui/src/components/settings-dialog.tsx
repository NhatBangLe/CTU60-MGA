"use client";

import * as React from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { ScrollArea, ScrollBar } from "./ui/scroll-area";

interface NavSetting {
  id: string;
  name: string;
  icon?: React.ReactNode;
  active?: {
    content: React.ReactNode;
  };
}

interface SettingsDialogProps {
  navSettings: NavSetting[];
  open: boolean;
  title?: string;
  description?: string;
  onOpenChange?: (open: boolean) => void;
  onNavChange?: (nav: NavSetting) => void;
}

export function SettingsDialog({
  navSettings,
  open,
  title,
  description,
  onOpenChange,
  onNavChange,
}: SettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild />
      <DialogContent className="overflow-hidden p-0 md:max-h-[600px] md:max-w-[700px] lg:max-w-[800px]">
        <DialogTitle className="sr-only">{title ?? "Settings"}</DialogTitle>
        <DialogDescription className="sr-only">
          {description ?? "Customize your settings here."}
        </DialogDescription>
        <SidebarProvider className="items-start">
          <Sidebar>
            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupContent>
                  <ScrollArea className="h-full md:max-h-[570px] md:max-w-[700px] lg:max-w-[800px]">
                    <SidebarMenu>
                      {navSettings.map((item) => (
                        <SidebarMenuItem key={item.id}>
                          <SidebarMenuButton
                            asChild
                            isActive={item.active !== undefined}
                            onClick={() => onNavChange?.(item)}
                          >
                            <a>
                              {item.icon}
                              <span className="truncate w-full md:max-w-[220px]">
                                {item.name}
                              </span>
                            </a>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                    </SidebarMenu>
                    <ScrollBar orientation="vertical" />
                  </ScrollArea>
                </SidebarGroupContent>
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>
          <main className="flex flex-1 flex-col overflow-hidden">
            <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
              <SidebarTrigger />
              <div className="flex items-center gap-2 px-4">
                <Breadcrumb>
                  <BreadcrumbList>
                    <BreadcrumbItem className="hidden md:block">
                      <BreadcrumbLink>{title ?? "Settings"}</BreadcrumbLink>
                    </BreadcrumbItem>
                    {navSettings.map((item) => {
                      if (item.active === undefined) return null;
                      return (
                        <React.Fragment key={item.name}>
                          <BreadcrumbSeparator className="hidden md:block" />
                          <BreadcrumbItem>
                            <BreadcrumbPage>{item.name}</BreadcrumbPage>
                          </BreadcrumbItem>
                        </React.Fragment>
                      );
                    })}
                  </BreadcrumbList>
                </Breadcrumb>
              </div>
            </header>
            <section className="w-full h-full py-3">
              {navSettings.map((item) => {
                if (item.active === undefined) return null;
                return (
                  <React.Fragment key={item.name}>
                    {item.active.content}
                  </React.Fragment>
                );
              })}
            </section>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  );
}
