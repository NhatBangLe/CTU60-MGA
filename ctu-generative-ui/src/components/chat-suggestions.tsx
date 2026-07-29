"use client";

import {
  buildImageSrc,
  ImageTemplate,
  templateGroups,
  templateSuggestions,
} from "@/templates";
import { Suggestion, Suggestions } from "./ai-elements/suggestion";
import { Badge } from "./ui/badge";
import { useTranslations } from "next-intl";
import { usePromptInputAttachments } from "./ai-elements/prompt-input";
import { getPublicAsset } from "@/lib/client/data";
import { toast } from "sonner";

interface ChatSuggestionsProps {
  onSuggestionClick?: (
    data:
      | { type: "text"; text: string }
      | { type: "image-template"; template: ImageTemplate }
  ) => void;
}

const ChatSuggestions = ({ onSuggestionClick }: ChatSuggestionsProps) => {
  const globalTrans = useTranslations("Global");
  const attachmentsCtx = usePromptInputAttachments();

  return (
    <Suggestions>
      {templateSuggestions.map((suggestion) => (
        <Suggestion
          key={suggestion.id}
          onClick={async () => {
            switch (suggestion.type) {
              case "image":
                const group = templateGroups.find(
                  (g) => g.id === suggestion.template.groupId
                )!;
                const template = group.templates.find(
                  (t) => t.id === suggestion.template.id
                )!;

                try {
                  const blob = await getPublicAsset(
                    buildImageSrc(template.image)
                  );
                  attachmentsCtx.add([
                    new File([blob], template.image.fileName, {
                      type: template.image.mimeType,
                    }),
                  ]);
                  onSuggestionClick?.({ type: "image-template", template });
                } catch (error) {
                  console.error(error);
                  toast(globalTrans("unknownError"));
                }
                break;

              case "text":
                onSuggestionClick?.({
                  type: "text",
                  text: suggestion.suggestion,
                });
                break;
            }
          }}
          suggestion={suggestion.suggestion}
        >
          <div className="flex flex-row flex-nowrap gap-1 items-center">
            <Badge variant={"default"}>{globalTrans(suggestion.type)}</Badge>
            <span>{suggestion.suggestion}</span>
          </div>
        </Suggestion>
      ))}
    </Suggestions>
  );
};

export default ChatSuggestions;
