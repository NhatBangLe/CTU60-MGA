import { PromptStatusResponse } from "../comfyui";
import { APIOptions } from "../type";
import { getFetchError } from "../utils";

/**
 * @throws `FetchError`
 */
export async function getComfyPromptStatus({
  promptId,
  jobId,
  options,
}: {
  promptId: string;
  jobId: string;
  options?: APIOptions;
}): Promise<PromptStatusResponse> {
  const res = await fetch(`/api/prompt/${promptId}/status`, {
    method: "GET",
    headers: {
      accept: "application/json",
      "X-Job-ID": jobId,
    },
    signal: options?.signal,
  });

  if (res.status === 200) return res.json();
  else {
    const error = await getFetchError(res);
    throw error;
  }
}

export async function getPublicAsset(url: string): Promise<Blob> {
  const response = await fetch(url, { method: "GET" });
  if (response.status === 200) return response.blob();
  else {
    const error = await getFetchError(response);
    throw error;
  }
}
