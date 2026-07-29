import {
  createUIMessageStream,
  createUIMessageStreamResponse,
  Output,
} from "ai";
import callCTUModel from "./_models/ctu";
import { nanoid } from "nanoid";
import { getTranslations } from "next-intl/server";
import { SemanticRouter } from "@/lib/routers";
import { consoleLog } from "@/lib/utils";
import { DefaultSemanticRouter } from "@/lib/routers/default";
import {
  APIOptions,
  ChatMessage,
  SupportedAction,
  SupportedActionSchema,
  SupportedModel,
} from "@/lib/type";
import { z } from "zod/v4";

export const semanticRouter: SemanticRouter = new DefaultSemanticRouter();

// @ts-ignore
async function routing(
  preferableAction: SupportedAction,
  messages: ChatMessage[],
  options?: APIOptions,
): Promise<z.infer<typeof SupportedActionSchema>> {
  const systemInstruction = `
### ROLE
You are a high-speed Task Routing Engine. Your ONLY purpose is to analyze user input and return a JSON object indicating the correct processing route.

### ROUTING LOGIC & BIAS
You must follow this internal priority logic to determine the 'route':
1. **Direct Intent:** If the user request explicitly matches one category (e.g., "draw," "make a video," "write a story"), route to that category immediately, regardless of the preference.
2. **Ambiguity / Tie-Breaker:** If the request is vague, generic ("help me"), or contains equal elements of multiple categories, use the **Preferable Route: '${preferableAction}'** as your deciding factor.
3. **Implicit Context:** If the request is about Can Tho University (CTU) facts or history, route to 'writing' unless an image/video is specifically requested.

### CATEGORIES
- 'writing': Text-based tasks, Q&A, CTU anniversary info, code, or general chat.
- 'generate_image': Requests for photos, illustrations, logos, or static visual creation.
- 'generate_video': Requests for motion, animation, or video file generation.

### OUTPUT RULES
- **JSON ONLY:** Output MUST be a single, valid JSON object. No markdown (\`\`\`json), no preamble, no "thought" tokens.
- **STRUCTURE:** {"route": "string"}
- **STRICTNESS:** Do not explain your choice. Do not use tool-calling syntax.

### EXAMPLE BEHAVIOR (Current Preference: ${preferableAction})
- User: "Draw a diamond logo for CTU" 
  -> {"route": "generate_image"} (Specific intent overrides bias)
- User: "Tell me a story"
  -> {"route": "writing"} (Specific intent overrides bias)
- User: "Can you help me with this?" 
  -> {"route": "${preferableAction}"} (Vague intent follows bias)
- User: "Do something interesting" 
  -> {"route": "${preferableAction}"} (Generic intent follows bias)
`;

  try {
    // only pass the lastest message
    const { output } = await semanticRouter.routing(messages.slice(-1), {
      output: Output.object({
        name: "feature-routing-schema",
        description: "Specifies the best system handler based on a user query.",
        schema: z.object({ route: SupportedActionSchema }),
      }),
      system: systemInstruction,
      ...options,
    });
    return output.route;
  } catch (error) {
    consoleLog("error", error);
    return "writing";
  }
}

export async function POST(req: Request) {
  const {
    messages,
    action,
  }: {
    messages?: ChatMessage[];
    model?: SupportedModel;
    action?: SupportedAction;
  } = await req.json();

  consoleLog("info", "Request headers:", req.headers);
  try {
    // const action = await routing(perferAction, messages, {
    //   signal: req.signal,
    // });
    consoleLog("info", "Action:", action);

    return callCTUModel({
      messages: messages ?? [],
      action: action ?? "writing",
      options: { signal: req.signal },
    });
  } catch (error) {
    consoleLog("error", `Error: ${JSON.stringify(error)}`);

    return createUIMessageStreamResponse({
      status: 200,
      statusText: "OK",
      stream: createUIMessageStream({
        async execute({ writer }) {
          const globalTrans = await getTranslations("Global");
          const chunkId = nanoid();

          writer.write({
            id: chunkId,
            type: "text-start",
          });
          writer.write({
            id: chunkId,
            type: "text-delta",
            delta: globalTrans("unknownError"),
          });
          writer.write({
            id: chunkId,
            type: "text-end",
          });
        },
      }),
    });
  }
}
