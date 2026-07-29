import { consoleLog } from "@/lib/utils";
import { tool } from "ai";
import { z } from "zod/v4";

interface SearchRequest {
  query: string;
  top_k?: number;
}

interface SearchResponse {
  query: string;
  results: Array<{
    text: string;
    score: number;
    metadata: Record<string, unknown>;
    rank: number;
  }>;
  total_found: number;
}

const inputSchema = z.object({
  query: z
    .string()
    .describe("The query needs to retrieve related information."),
});

const outputSchema = z.object({
  query: z.string().describe("The requested query."),
  results: z
    .array(
      z.object({
        text: z.string().describe("The content of the result."),
        score: z.number().describe("The score of the result."),
        metadata: z
          .record(z.string(), z.unknown())
          .describe("The metadata of the result."),
        rank: z.number().describe("The rank of the result."),
      }),
    )
    .describe("The top-k related results."),
});

const retrievalTool = tool<
  z.infer<typeof inputSchema>,
  z.infer<typeof outputSchema>
>({
  title: "get_related_information",
  description: "Retrieve related information for a user query",
  type: "function",
  inputSchema,
  outputSchema,
  execute: async function (params, options) {
    const serverUrl = process.env.TOOL_SERVER_URL;
    if (serverUrl === undefined)
      throw new Error("Cannot find TOOL_SERVER_URL environment variable.");

    try {
      const response = await fetch(`${serverUrl}/search`, {
        method: "POST",
        body: JSON.stringify({
          query: params.query,
          top_k: 5,
        } as SearchRequest),
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
        signal: options.abortSignal,
      });
      const data: SearchResponse = await response.json();

      return {
        query: data.query,
        results: data.results,
      };
    } catch (error) {
      consoleLog("warn", error);
      throw new Error("Cannot retrieve data from server.");
    }
  },
});

export default retrievalTool;
