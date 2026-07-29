import { FileUIPart } from "ai";
import { ChatMessage } from "@/lib/type";
import { consoleLog } from "@/lib/utils";
import { QwenImageEditPrompt } from "@/lib/comfyui/workflows/qwen-image-edit";
import { ChatMessageUtils } from "@/lib/chatbot";
import { GenerateImageHandler } from ".";

export default class QwenImageEditPromptHandler
  implements GenerateImageHandler
{
  /**
   * {@inheritDoc}
   * * @remarks
   * This implementation supports a maximum of 3 input images.
   * If more than 3 images are provided, a warning is logged, and only the first 3 are used.
   */
  getPrompt({
    images,
    prompt,
  }: {
    images?: Array<string | undefined>;
    prompt?: string;
  }) {
    const textPart = ChatMessageUtils.validateTextPart({
      type: "text",
      text: prompt ?? "",
    });
    const totalImages = images?.length ?? 0;
    if (totalImages > 3)
      consoleLog(
        "warn",
        `QwenImageEditPrompt_getPrompt: Too many images. (maximum 3, current ${totalImages})`
      );

    consoleLog(
      "debug",
      `QwenImageEditPrompt_getPrompt - Input prompt: ${JSON.stringify({
        text: textPart.text,
        numOfImg: totalImages,
      })}`
    );
    return new QwenImageEditPrompt({
      image1: images?.at(0),
      image2: images?.at(1),
      image3: images?.at(2),
      prompt: textPart.text,
    });
  }

  /**
   * {@inheritDoc}
   * * @remarks
   * Filters message parts for type 'file' with 'image/' media types.
   * Warns if more than 3 images are found.
   */
  getPromptByMessage(message: ChatMessage) {
    const textPart = ChatMessageUtils.validateTextPart(
      message.parts.find((part) => part.type === "text")
    );
    const imgParts = message.parts.filter(
      (part) => part.type === "file" && part.mediaType.includes("image/")
    ) as FileUIPart[];
    if (imgParts.length > 3)
      consoleLog(
        "warn",
        `QwenImageEditPrompt_getPromptByMessage: Too many images. (maximum 3, current ${imgParts.length})`
      );

    consoleLog(
      "debug",
      `QwenImageEditPrompt_getPromptByMessage - Input prompt: ${JSON.stringify({
        text: textPart.text,
        numOfImg: imgParts.length,
      })}`
    );
    return new QwenImageEditPrompt({
      image1: imgParts.at(0)?.url,
      image2: imgParts.at(1)?.url,
      image3: imgParts.at(2)?.url,
      prompt: textPart.text,
    });
  }
}
