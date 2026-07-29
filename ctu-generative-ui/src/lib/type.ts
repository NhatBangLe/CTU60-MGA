import { ChatTools } from "@/tools";
import { UIDataTypes, UIMessage } from "ai";
import { z } from "zod/v4";

export type MessageMetadata =
  | {
      type: "chat";
    }
  | {
      type: "select-template";
      template: {
        name: string;
      };
    }
  | {
      type: "generate-media";
      status: "request" | "queued" | "finished" | "aborted";
      data?: { promptId: string; jobId: string };
    };

export type ChatMessage = UIMessage<MessageMetadata, UIDataTypes, ChatTools>;
export const SupportedActionSchema = z.enum([
  "writing",
  "generate_image",
  "generate_video",
]).describe(`Specifies the route type:
- 'writing' for new text generation.
- 'generate_image' for image generation.
- 'generate_video' for video generation.`);
export type SupportedAction = z.infer<typeof SupportedActionSchema>;
export type SupportedModel = "ctu";

export interface APIOptions {
  signal?: AbortSignal;
}
