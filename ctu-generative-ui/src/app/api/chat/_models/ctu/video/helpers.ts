import { ComfyHandler } from "@/lib/comfyui";
import { ChatMessage } from "@/lib/type";
import { ImageTemplate } from "@/templates";
import { consoleLog } from "@/lib/utils";
import { Txt2VideoPrompt } from "@/lib/comfyui/workflows/txt2video";
import { Img2VideoPrompt } from "@/lib/comfyui/workflows/img2video";
import { ChatMessageUtils } from "@/lib/chatbot";

/**
 * Handles the "Text-to-Video" generation workflow.
 *
 * This function extracts the text prompt from the user's message using `validateTextPart`,
 * logs the intent for debugging, and returns a constructed `Txt2VideoPrompt` object.
 *
 * @param params.message - The `ChatMessage` object containing the user's text prompt.
 * @returns A new instance of `Txt2VideoPrompt` initialized with the user's text.
 * @throws {ValidationError} If the message does not contain a valid text prompt.
 */
export function handleTxt2Vid({ message }: { message: ChatMessage }) {
  const textPart = ChatMessageUtils.validateTextPart(
    message.parts.find((part) => part.type === "text")
  );

  consoleLog(
    "debug",
    `handleTxt2Vid - Input prompt: ${JSON.stringify({
      text: textPart.text,
      numOfImg: 0,
    })}`
  );
  return new Txt2VideoPrompt({ prompt: textPart.text });
}

/**
 * Handles the "Image-to-Video" generation workflow.
 *
 * This function constructs a video generation request by combining a text prompt from the user's
 * message with a specific base image. It resolves the image source from either a direct URL string
 * or an `ImageTemplate` object.
 *
 * @param params.message - The `ChatMessage` object containing the user's text prompt.
 * @param params.baseImage - The source image to animate. Can be a string URL or an `ImageTemplate` object.
 * @returns A new instance of `Img2VideoPrompt` initialized with the resolved image path and text prompt.
 * @throws {ValidationError} If the message is missing a valid text prompt.
 */
export function handleImg2Vid({
  message,
  baseImage,
}: {
  message: ChatMessage;
  baseImage: string | ImageTemplate;
}) {
  const textPart = ChatMessageUtils.validateTextPart(
    message.parts.find((part) => part.type === "text")
  );

  consoleLog(
    "debug",
    `handleImg2Vid - Input prompt: ${JSON.stringify({
      text: textPart.text,
      numOfImg: 1,
    })}`
  );
  return new Img2VideoPrompt({
    image:
      typeof baseImage === "string"
        ? baseImage
        : ComfyHandler.getImageTemplatePath(baseImage),
    prompt: textPart.text,
  });
}
