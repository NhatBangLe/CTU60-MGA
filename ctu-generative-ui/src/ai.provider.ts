import {
  createProviderRegistry,
  customProvider,
  defaultSettingsMiddleware,
  wrapLanguageModel,
} from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";

const openaiCompatible = createOpenAICompatible({
  name: "hosted-provider",
  apiKey: process.env.LLM_PROVIDER_API_KEY,
  baseURL: process.env.LLM_PROVIDER_URL ?? "http://127.0.0.1:8080/v1",
  includeUsage: false, // Include usage information in streaming responses
  supportsStructuredOutputs: true,
});

export const modelRegistry = createProviderRegistry(
  {
    ctu: customProvider({
      languageModels: {
        routing: wrapLanguageModel({
          model: openaiCompatible("deepseek-r1:8b"),
          middleware: defaultSettingsMiddleware({
            settings: {
              maxOutputTokens: 4096,
            },
          }),
        }),
        writing: wrapLanguageModel({
          model: openaiCompatible("gpt-oss:20b"),
          middleware: defaultSettingsMiddleware({
            settings: {
              maxOutputTokens: 4096,
              temperature: 0.6,
            },
          }),
        }),
      },
    }),
  },
  { separator: " > " },
);
