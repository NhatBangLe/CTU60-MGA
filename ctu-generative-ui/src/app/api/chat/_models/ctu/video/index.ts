import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  Output,
} from "ai";
import { z } from "zod/v4";
import { HandlingError, ValidationError } from "@/lib/errors";
import { getTranslations } from "next-intl/server";
import { nanoid } from "nanoid";
import { consoleLog } from "@/lib/utils";
import { APIOptions, ChatMessage } from "@/lib/type";
import { semanticRouter } from "../../../route";
import { ComfyHandler, ComfyPrompt } from "@/lib/comfyui";
import { handleImg2Vid, handleTxt2Vid } from "./helpers";
import { ChatMessageUtils } from "@/lib/chatbot";

const ComfyVideoRouteEnum = z.enum(["txt2vid", "contextual_img2vid"])
  .describe(`Specifies the route based on user intent and contextual flags:
- **txt2vid**: \`has_text_input: true\` AND \`has_image_input: false\` AND creates a **new video**.
- **contextual_img2vid**: \`has_text_input: true\` AND \`has_image_input: false\` AND refers to a **previously generated image** to ANIMATE it.`);

/**
 * @type `txt2vid` Generate a new video with `only-text` prompt.
 * @type `img2vid` Generate a new video or animate an image with `text and an uploaded image` prompt.
 * @type `contextual_img2vid` Animate the previous generated image with `only-text` prompt.
 */
type ComfyVideoRoute = z.infer<typeof ComfyVideoRouteEnum> | "img2vid";

async function routing(
  messages: ChatMessage[],
  options?: APIOptions,
): Promise<z.infer<typeof ComfyVideoRouteEnum>> {
  const userPrompt = ChatMessageUtils.findLastUserPrompt(messages);
  if (userPrompt === null)
    throw new ValidationError(
      "Cannot specify the best handling route because no user prompt is found.",
    );

  const systemInstruction: string = `You are an expert **Context-Aware Request Router and Intent Classifier**.

Your **MISSION** is to analyze the user's latest input to determine which of the two defined downstream handling systems (Routes) is the most appropriate. Your response **must** be a single, structured JSON object.

---

**AVAILABLE ROUTES & CRITERIA:**

| Route Name | Criteria for Selection |
| :--- | :--- |
| **txt2vid** | The user provides a text prompt to CREATE a **new video** from scratch. |
| **contextual_img2vid** | The user refers to a **previously generated image** (e.g., using "this," "that," or "it") and provides a prompt to **animate** it or turn it into a video. |

---

**ROUTE EXAMPLES:**

* **txt2vid:**
    * Prompt: "Generate a cinematic video of a cyberpunk city with rain falling."
    * Prompt: "Make a video of a cat dancing."
* **contextual_img2vid:**
    * Prompt: "Make that image move." 
    * Prompt: "Turn this into a 4 second video."
    * Prompt: "Animate the last picture you made."

---

**OUTPUT FORMAT RULES:**

1.  Your output **must** be a single JSON object.
2.  The JSON object **must** contain a single key:
    * "route": (string) The name of the selected route from the table above (e.g., "txt2vid", or "contextual_img2vid").
3.  **Do NOT** include any commentary, explanation, or text outside of the JSON object.`;

  try {
    const { output } = await semanticRouter.routing(messages.slice(-1), {
      output: Output.object({
        name: "video-routing-schema",
        description: "Video generation schema.",
        schema: z.object({ route: ComfyVideoRouteEnum }),
      }),
      system: systemInstruction,
      ...options,
    });
    return output.route;
  } catch (error) {
    consoleLog("error", error);
    return "txt2vid";
  }
}

export async function generateVideo({
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
          const latestMessage = messages.at(-1)!;
          const userPrompt = ChatMessageUtils.findLastUserPrompt(messages);
          const route: ComfyVideoRoute = userPrompt?.userImage
            ? "img2vid"
            : await routing(messages, options);

          consoleLog("info", `CTU Platform - generateVideo: ${route}`);

          writer.write({
            id: chunkId,
            type: "text-start",
          });
          writer.write({
            id: chunkId,
            type: "text-delta",
            delta: chatTrans("beforeReceivedPromptId"),
          });

          let prompt: ComfyPrompt;
          switch (route) {
            case "txt2vid": {
              prompt = handleTxt2Vid({
                message: latestMessage,
              });
              break;
            }

            case "img2vid": {
              if (
                userPrompt?.text === undefined ||
                userPrompt?.userImage === undefined
              )
                throw new HandlingError(
                  "img2vid: Cannot generate a new video because of bad routing.",
                );

              prompt = handleImg2Vid({
                message: latestMessage,
                baseImage: userPrompt?.userImage,
              });
              break;
            }

            case "contextual_img2vid": {
              const lastGeneratedImagePart =
                ChatMessageUtils.findLastGeneratedFile(messages, "image/");
              if (lastGeneratedImagePart !== null)
                prompt = handleImg2Vid({
                  message: latestMessage,
                  baseImage: lastGeneratedImagePart.url,
                });
              else
                throw new ValidationError(
                  "contextual_img2vid: Cannot generate a new video because of bad routing.",
                );
              break;
            }
          }
          if (prompt === undefined)
            throw new HandlingError(
              "Video content is not generated because the system cannot detect which task should be performed.",
            );

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
          consoleLog("error", `Streaming video-gen error:`, error);

          if ((error as { name?: string }).name !== "AbortError") {
            writer.write({
              id: chunkId,
              type: "text-delta",
              delta: ` ${chatTrans("generateVideoError")}`,
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
