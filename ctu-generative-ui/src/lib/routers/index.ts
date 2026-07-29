import {
  CallSettings,
  GenerateTextResult,
  ModelMessage,
  Output,
  Prompt,
  ToolSet,
} from "ai";
import { APIOptions, ChatMessage } from "../type";

export interface SemanticRouter {
  convertUIMessages(messages: ChatMessage[]): Promise<ModelMessage[]>;
  routing<OUTPUT = any, PARTIAL = any, ELEMENT = any>(
    messages: ChatMessage[],
    options: Omit<CallSettings, "stopSequences" | "abortSignal"> &
      Omit<Prompt, "prompt" | "messages"> &
      APIOptions & {
        output: Output.Output<OUTPUT, PARTIAL, ELEMENT>;
      },
  ): Promise<
    GenerateTextResult<ToolSet, Output.Output<OUTPUT, PARTIAL, ELEMENT>>
  >;
}
