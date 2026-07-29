import { SettingsDialog } from "@/components/settings-dialog";
import { ImageTemplate, templateGroups } from "@/templates";
import { useState } from "react";
import { TemplateCarousel } from "./template-carousel";
import { useTranslations } from "next-intl";

type TemplateSettings = Parameters<typeof SettingsDialog>[0]["navSettings"];

interface TemplateDialogProps {
  open: boolean;
  onClose?: () => void;
  onTemplateClick?: (template: ImageTemplate) => void;
}

const TemplateDialog = ({
  open,
  onClose,
  onTemplateClick,
}: TemplateDialogProps) => {
  const chatTrans = useTranslations("Chat");

  const [templates, setTemplates] = useState<TemplateSettings>(
    templateGroups.map((group, index) => ({
      id: group.id,
      name: group.name,
      active:
        index === 0
          ? {
              content: (
                <TemplateCarousel
                  templates={group.templates}
                  onTemplateClick={onTemplateClick}
                />
              ),
            }
          : undefined,
    }))
  );

  return (
    <SettingsDialog
      open={open}
      title={chatTrans("templateDialogTitle")}
      description={chatTrans("templateDialogDescription")}
      navSettings={templates}
      onOpenChange={(open) => !open && onClose?.()}
      onNavChange={(nextNav) => {
        setTemplates((pre) =>
          pre.map((nav) => {
            if (nav.id === nextNav.id) {
              if (nextNav.active) return nextNav;
              else {
                const group = templateGroups.find((g) => g.id === nextNav.id);
                return {
                  ...nav,
                  active: {
                    content: (
                      <TemplateCarousel
                        templates={group?.templates ?? []}
                        onTemplateClick={onTemplateClick}
                      />
                    ),
                  },
                };
              }
            }
            return { ...nav, active: undefined };
          })
        );
      }}
    />
  );
};

export default TemplateDialog;
