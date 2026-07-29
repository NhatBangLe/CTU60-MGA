import {
  generateText,
  ModelMessage,
  streamText,
  convertToModelMessages,
  ToolLoopAgent,
} from "ai";
import { APIOptions, ChatMessage } from "@/lib/type";
import { Chatbot, systemInstruction } from "@/lib/chatbot";
import { toolSet } from "@/tools";
import { modelRegistry } from "@/ai.provider";

export default class CTUChatbot implements Chatbot {
  private readonly agent: ToolLoopAgent;

  constructor() {
    this.agent = new ToolLoopAgent({
      instructions: systemInstruction,
      model: modelRegistry.languageModel("ctu > writing"),
      tools: toolSet,
      // stopWhen: [stepCountIs(20)], // default
    });
  }

  async convertUIMessages(messages: ChatMessage[]): Promise<ModelMessage[]> {
    return convertToModelMessages(messages);
  }

  async generateText(
    messages: ChatMessage[],
    options?: APIOptions,
  ): Promise<ReturnType<typeof generateText>> {
    const result = this.agent.generate({
      messages: await this.convertUIMessages(messages.slice(-2)), // take only the second to last message of the conversation
      abortSignal: options?.signal,
    });
    return result;
  }

  async streamText(
    messages: ChatMessage[],
    options?: APIOptions,
  ): Promise<ReturnType<typeof streamText>> {
    const result = this.agent.stream({
      messages: await this.convertUIMessages(messages.slice(-2)),
      abortSignal: options?.signal,
    });
    return result;
  }
}
