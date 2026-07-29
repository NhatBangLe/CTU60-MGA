import { ImageTemplate } from "@/templates";
import { NotFoundError, ValidationError } from "../errors";
import { APIOptions } from "../type";
import { getFetchError } from "../utils";

export interface ComfyPrompt {
  getWorkflow: () => unknown;
}

export interface PromptStatusResponse {
  promptId: string;
  status: "pending" | "processing" | "completed" | "failed" | "interrupted";
  progress: number;
  file?: {
    url: string;
    mimeType: string;
  } | null;
}

export class ComfyHandler {
  static getComfyUrl() {
    const rawUrl = process.env.COMFYUI_API_URL;
    if (rawUrl === undefined)
      throw new NotFoundError(
        "Cannot find COMFYUI_API_URL environment variable."
      );
    const url = URL.parse(rawUrl);
    if (url === null)
      throw new ValidationError("The value of COMFYUI_API_URL is not an URL.");
    return url;
  }

  /**
   * @throws `FetchError`
   */
  static async generateContent({
    prompt,
    options,
  }: {
    prompt: ComfyPrompt;
    options?: APIOptions;
  }) {
    const comfyUrl = this.getComfyUrl();
    const jobId = crypto.randomUUID();
    const workflow = prompt.getWorkflow();
    const response = await fetch(
      `${comfyUrl.toString()}api/v1/comfy/generate`,
      {
        method: "POST",
        body: JSON.stringify({ prompt: workflow }),
        headers: {
          "Content-Type": "application/json",
          "X-Job-ID": jobId,
        },
        signal: options?.signal,
      }
    );

    if (response.status === 201) {
      const { promptId }: { promptId: string } = await response.json();
      return {
        status: response.status,
        statusText: response.statusText,
        data: { jobId, promptId },
      };
    } else throw await getFetchError(response);
  }

  /**
   * @throws `FetchError`
   */
  static async getPromptStatus({
    promptId,
    jobId,
    options,
  }: {
    promptId: string;
    jobId: string;
    options?: APIOptions;
  }): Promise<{
    status: number;
    statusText: string;
    data: PromptStatusResponse;
  }> {
    const comfyUrl = this.getComfyUrl();
    const response = await fetch(
      `${comfyUrl.toString()}api/v1/comfy/${promptId}/status`,
      {
        method: "GET",
        headers: {
          accept: "application/json",
          "X-Job-ID": jobId,
        },
        signal: options?.signal,
      }
    );

    if (response.status === 200)
      return {
        status: response.status,
        statusText: response.statusText,
        data: await response.json(),
      };
    else throw await getFetchError(response);
  }

  static getImageTemplatePath(template: ImageTemplate) {
    return `./${
      template.image.subfolder ? `${template.image.subfolder}/` : ""
    }${template.image.fileName}`;
  }
}
