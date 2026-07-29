import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  Output,
} from "ai";
import { getTranslations } from "next-intl/server";
import { nanoid } from "nanoid";
import { consoleLog } from "@/lib/utils";
import { APIOptions, ChatMessage } from "@/lib/type";
import { ComfyHandler, ComfyPrompt } from "@/lib/comfyui";
import QwenImageEditPromptHandler from "./qwen-image-edit-handler";
import { semanticRouter } from "../../../route";
import { ValidationError } from "@/lib/errors";
import { ChatMessageUtils } from "@/lib/chatbot";
import { z } from "zod/v4";

export interface GenerateImageHandler {
  /**
   * Generates a ComfyUI-compatible prompt object by extracting relevant
   * text and media content from a chat message.
   * * Implementations should handle parsing the message parts to locate
   * the primary text prompt and any attached image files.
   *
   * @param message - The chat message containing text parts and/or file attachments.
   * @returns A `ComfyPrompt` object configured based on the message content.
   * @throws {ValidationError} If the input data is invalid.
   */
  getPromptByMessage(message: ChatMessage): ComfyPrompt;
  /**
   * Generates a ComfyUI-compatible prompt object using explicit parameters.
   * * This method allows for generating prompts without a full `ChatMessage` object,
   * useful for programmatic calls or when inputs are already separated.
   *
   * @param data - The input data configuration.
   * @param data.prompt - The text description or instruction for image generation.
   * @param data.images - (Optional) An array of image Web or Data URLs or paths to be used as input references.
   * @returns A `ComfyPrompt` object configured with the provided text and images.
   * @throws {ValidationError} If the input data is invalid.
   */
  getPrompt(data: {
    images?: Array<string | undefined>;
    prompt?: string;
  }): ComfyPrompt;
}
const promptHandler: GenerateImageHandler = new QwenImageEditPromptHandler();

const GenerateImageRouteEnum = z.enum([
  "generate_image",
  "edit_generated_image",
]).describe(`Specifies the route based on user intent and contextual flags:
- **generate_image**: Handles any request to create or generate images, regardless of whether the input is text-only or includes attached images.
- **edit_generated_image**: Handles requests where the text prompt explicitly refers to or mentions the **last generated image** in the conversation history to modify it.`);

async function routing(
  messages: ChatMessage[],
  options?: APIOptions,
): Promise<z.infer<typeof GenerateImageRouteEnum>> {
  const userPrompt = ChatMessageUtils.findLastUserPrompt(messages);
  if (userPrompt === null)
    throw new ValidationError(
      "Cannot specify the best handling route because no user prompt is found.",
    );

  const systemInstruction: string = `You are an expert **Context-Aware Request Router and Intent Classifier**.

Your **MISSION** is to analyze the user's latest input to determine which of the two downstream handling systems (Routes) is the most appropriate. Your response **must** be a single, structured JSON object.

---

**AVAILABLE ROUTES & CRITERIA:**

| Route Name | Criteria for Selection |
| :--- | :--- |
| **generate_image** | Handles requests to create or generate images. This includes generating from scratch OR generating based on a file attached in the current prompt. |
| **edit_generated_image** | The user's text prompt explicitly refers to or mentions the **last previously generated image** (from conversation history) and asks to MODIFY it. |

---

**ROUTE EXAMPLES:**

* **generate_image:**
    * Prompt: \`"Generate a photorealistic image of an astronaut riding a horse on Mars."\`
    * *Reasoning:* Request for new image creation.
* **generate_image:**
    * Prompt: \`"Use this attached sketch to create a 3D render of a superhero."\`
    * *Reasoning:* Request for creation using a provided attachment.
* **edit_generated_image:**
    * Prompt: \`"That's great, now can you make the astronaut's helmet golden?"\`
    * *Reasoning:* Modification request targeting the previously generated result (contextual reference to "the astronaut").
* **edit_generated_image:**
    * Prompt: \`"Remove the background from the image you just made."\`
    * *Reasoning:* Explicit reference to the previous generation.

---

**OUTPUT FORMAT RULES:**

1.  Your output **must** be a single JSON object.
2.  The JSON object **must** contain a single key:
    * \`"route"\`: (string) The name of the selected route ("generate_image", or "edit_generated_image").
3.  **Do NOT** include any commentary, explanation, or text outside of the JSON object.`;

  try {
    const history = messages.slice(-1); // take only the latest message in the conversation.
    const { output } = await semanticRouter.routing(history, {
      output: Output.object({
        name: "image-routing-schema",
        description: "Image generation schema.",
        schema: z.object({ route: GenerateImageRouteEnum }),
      }),
      system: systemInstruction,
      signal: options?.signal,
    });
    return output.route;
  } catch (error) {
    consoleLog("error", error);
    return "generate_image";
  }
}

export async function generateImage({
  messages,
  options,
}: {
  messages: ChatMessage[];
  options?: APIOptions;
}) {
  const chatTrans = await getTranslations("Chat");

  return createUIMessageStreamResponse({
    status: 200,
    statusText: "OK",
    stream: createUIMessageStream<ChatMessage>({
      async execute({ writer }) {
        const chunkId = nanoid();

        try {
          const route = await routing(messages, options);

          const latestMessage = messages.at(-1)!;
          let prompt: ComfyPrompt;
          switch (route) {
            case "generate_image": {
              prompt = promptHandler.getPromptByMessage(latestMessage);
              break;
            }

            case "edit_generated_image": {
              const mimeType = "image/";
              const textPart = latestMessage.parts.find(
                (part) => part.type === "text",
              );
              const inputImageUrls = ChatMessageUtils.getFilePartsByMIME(
                latestMessage,
                mimeType,
              ).map((part) => part.url);
              const generatedImagePart = ChatMessageUtils.findLastGeneratedFile(
                messages,
                mimeType,
              );
              prompt = promptHandler.getPrompt({
                images: [...inputImageUrls, generatedImagePart?.url],
                prompt: textPart?.text,
              });
              break;
            }
          }

          writer.write({
            id: chunkId,
            type: "text-start",
          });
          writer.write({
            id: chunkId,
            type: "text-delta",
            delta: chatTrans("beforeReceivedPromptId"),
          });

          writer.write({
            type: "message-metadata",
            messageMetadata: {
              type: "generate-media",
              status: "request",
            },
          });

          const response = await ComfyHandler.generateContent({
            prompt,
            options,
          });

          writer.write({
            id: chunkId,
            type: "text-delta",
            delta: ` ${chatTrans("afterReceivedPromptId")}`,
          });
          writer.write({
            id: chunkId,
            type: "text-end",
          });
          writer.write({
            type: "message-metadata",
            messageMetadata: {
              type: "generate-media",
              status: "queued",
              data: response.data,
            },
          });
        } catch (error) {
          consoleLog("error", `Streaming image-gen error:`, error);

          if ((error as { name?: string }).name !== "AbortError") {
            writer.write({
              id: chunkId,
              type: "text-delta",
              delta: ` ${chatTrans("generateImageError")}`,
            });
            writer.write({
              id: chunkId,
              type: "text-end",
            });
          } else writer.write({ type: "abort" });
        }
      },
    }),
  });
}
