"use server";

import { APIOptions, ChatMessage, SupportedAction } from "@/lib/type";
import { generateImage } from "./image";
import { generateVideo } from "./video";
import CTUChatbot from "@/lib/chatbot/ctu";
import { InvalidToolInputError, NoSuchToolError } from "ai";
import { consoleLog } from "@/lib/utils";

export type CTUModelAction = SupportedAction;

const chatbot = new CTUChatbot();

export async function streamTextFromCTUChatbot(
  messages: ChatMessage[],
  options?: APIOptions,
) {
  return chatbot.streamText(messages, options);
}

export default async function callCTUModel({
  messages,
  action,
  options,
}: {
  messages: ChatMessage[];
  action: CTUModelAction;
  options?: APIOptions;
}) {
  switch (action) {
    case "writing": {
      const stream = await streamTextFromCTUChatbot(messages, options);
      return stream.toUIMessageStreamResponse({
        sendSources: false,
        sendReasoning: true,
        onError: (error) => {
          consoleLog("warn", error);

          if (NoSuchToolError.isInstance(error)) {
            return "The model tried to call an unknown tool.";
          } else if (InvalidToolInputError.isInstance(error)) {
            return "The model called a tool with invalid inputs.";
          } else {
            return "An unknown error occurred.";
          }
        },
      });
    }

    case "generate_image":
      return generateImage({ messages, options });

    case "generate_video":
      return generateVideo({ messages, options });
  }
}
