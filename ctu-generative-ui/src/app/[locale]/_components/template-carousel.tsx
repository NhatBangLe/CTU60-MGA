"use client";

import * as React from "react";

import {
  Carousel,
  CarouselApi,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { buildImageSrc, ImageTemplate } from "@/templates";
import { usePromptInputAttachments } from "@/components/ai-elements/prompt-input";
import { getPublicAsset } from "@/lib/client/data";
import { toast } from "sonner";
import { nanoid } from "nanoid";

type TemplateCarouselProps = Parameters<typeof Carousel>[0] & {
  templates: ImageTemplate[];
  onTemplateClick?: (template: ImageTemplate) => PromiseLike<void> | void;
};

const fileConfig = {
  accept: ".png,.jpg,.jpeg",
  multiple: false,
  maxFiles: 1,
};

export function TemplateCarousel({
  templates,
  className,
  onTemplateClick,
  ...props
}: TemplateCarouselProps) {
  const [fileInputKey, setFileInputKey] = React.useState(nanoid());
  const globalTrans = useTranslations("Global");
  const attachmentsCtx = usePromptInputAttachments();
  const [api, setApi] = React.useState<CarouselApi>();
  const [current, setCurrent] = React.useState(0);
  const [count, setCount] = React.useState(0);
  const [selectedTemplate, setSelectedTemplate] =
    React.useState<ImageTemplate>();
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    if (!api) {
      return;
    }
    setCount(api.scrollSnapList().length);
    setCurrent(api.selectedScrollSnap() + 1);
    api.on("select", () => {
      setCurrent(api.selectedScrollSnap() + 1);
    });
  }, [api]);

  return (
    <div className="flex flex-col items-center w-full h-full">
      <div
        className="text-muted-foreground py-2 text-center text-sm"
        role="pagination"
      >
        {`${globalTrans("page")} ${current} - ${count}`}
      </div>

      <Carousel
        className={cn("max-w-xs", className)}
        setApi={setApi}
        {...props}
      >
        <CarouselContent>
          {templates.map((template) => (
            <CarouselItem key={template.id}>
              <Card>
                <CardHeader>
                  <CardTitle>{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                  <CardAction>
                    <input
                      ref={fileInputRef}
                      key={fileInputKey}
                      className="hidden"
                      type="file"
                      multiple={fileConfig.multiple}
                      accept={fileConfig.accept}
                      onChange={async (e) => {
                        if (!selectedTemplate) return;
                        const fileList = e.target.files;
                        if (!fileList || fileList.length === 0) return;

                        if (fileList.length > fileConfig.maxFiles)
                          toast(
                            globalTrans("maxFiles", {
                              max: fileConfig.maxFiles,
                            }),
                          );
                        else {
                          try {
                            const blob = await getPublicAsset(
                              buildImageSrc(selectedTemplate.image),
                            );

                            attachmentsCtx.add([
                              fileList.item(0)!, // already check above
                              new File(
                                [blob],
                                selectedTemplate.image.fileName,
                                {
                                  type: selectedTemplate.image.mimeType,
                                },
                              ),
                            ]);
                            onTemplateClick?.(selectedTemplate);
                          } catch (error) {
                            console.error(error);
                            toast(globalTrans("unknownError"));
                          }
                        }

                        setFileInputKey(nanoid());
                      }}
                    />
                    <Button
                      className="cursor-pointer"
                      onClick={() => {
                        fileInputRef.current?.click();
                        setSelectedTemplate(template);
                      }}
                    >
                      {globalTrans("select")}
                    </Button>
                  </CardAction>
                </CardHeader>
                <CardContent className="flex aspect-square items-center justify-center">
                  {
                    /* eslint-disable @next/next/no-img-element */
                    <img
                      alt={template.name}
                      src={buildImageSrc(template.image)}
                      className="w-full max-w-3xs h-auto max-h-96"
                    />
                  }
                </CardContent>
              </Card>
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>
    </div>
  );
}
