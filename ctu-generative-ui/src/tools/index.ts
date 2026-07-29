import { InferUITools, ToolSet } from "ai";
import retrievalTool from "./retrieval";

const tools = {
  retrievalTool,
};

export type ChatTools = InferUITools<typeof tools>;

export const toolSet = tools as ToolSet;
