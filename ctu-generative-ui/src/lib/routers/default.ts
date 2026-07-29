import { modelRegistry } from "@/ai.provider";
import {
  CallSettings,
  LanguageModel,
  ModelMessage,
  Prompt,
  convertToModelMessages,
  generateText,
  Output,
  GenerateTextResult,
  ToolSet,
} from "ai";
import { SemanticRouter } from "@/lib/routers";
import { APIOptions, ChatMessage } from "@/lib/type";

export class DefaultSemanticRouter implements SemanticRouter {
  readonly routingModel: LanguageModel;

  constructor() {
    this.routingModel = modelRegistry.languageModel("ctu > routing");
  }

  async routing<OUTPUT = any, PARTIAL = any, ELEMENT = any>(
    messages: ChatMessage[],
    options: Omit<CallSettings, "stopSequences" | "abortSignal"> &
      Omit<Prompt, "prompt" | "messages"> &
      APIOptions & {
        output: Output.Output<OUTPUT, PARTIAL, ELEMENT>;
      },
  ): Promise<
    GenerateTextResult<ToolSet, Output.Output<OUTPUT, PARTIAL, ELEMENT>>
  > {
    const convertedMsgs = await this.convertUIMessages(messages);
    const promise = generateText({
      ...options,
      prompt: undefined,
      model: this.routingModel,
      messages: convertedMsgs,
      abortSignal: options?.signal,
    });

    return promise;
  }

  async convertUIMessages(messages: ChatMessage[]): Promise<ModelMessage[]> {
    return convertToModelMessages(messages);
  }
}
