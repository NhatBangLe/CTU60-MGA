"use client";

import { Shimmer } from "@/components/ai-elements/shimmer";
import { getComfyPromptStatus } from "@/lib/client/data";
import { consoleLog } from "@/lib/utils";
import { useTranslations } from "next-intl";
import { useState, useEffect } from "react";

type PollingStatus = "initialize" | "processing" | "completed" | "error";
const pollingInterval = 5000; // 5 seconds

export function PollingMedia({
  jobId,
  promptId,
  abort = false,
  onMediaSuccess,
}: {
  abort?: boolean;
  jobId: string;
  promptId: string;
  onMediaSuccess?: (data: { url: string; mimeType: string }) => void;
}) {
  const chatTrans = useTranslations("Chat");
  const globalTrans = useTranslations("Global");
  const [status, setStatus] = useState<PollingStatus>("initialize");
  const [pollProcess, setPollProcess] = useState(0);
  const [abortController, setAbortController] =
    useState<AbortController | null>(new AbortController());

  useEffect(() => {
    if (abortController === null) return;
    if (abort === true) {
      const controller = abortController;
      setAbortController(null);
      controller.abort();
    }
  }, [abort, abortController]);

  useEffect(() => {
    async function polling() {
      if (status === "completed") return;

      try {
        const data = await getComfyPromptStatus({
          jobId,
          promptId,
          options: { signal: abortController?.signal },
        });
        if (data.status === "completed") {
          if (data.file) {
            onMediaSuccess?.(data.file);
            setStatus("completed");
          } else setStatus("error");
        } else {
          switch (data.status) {
            case "pending":
            case "processing": {
              setPollProcess(data.progress);
              setStatus("processing");
              setTimeout(polling, pollingInterval);
              break;
            }
            case "failed":
            case "interrupted": {
              setStatus("error");
              break;
            }
          }
        }
      } catch (err) {
        consoleLog("warn", JSON.stringify(err));
        if ((err as { name?: string }).name === "AbortError") return;
        setStatus("error");
      }
    }

    const timeout = setTimeout(polling, pollingInterval);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, promptId]);

  return (
    <>
      {!abort && status !== "completed" && (
        <Shimmer className="px-1" duration={1} key={`metadata-${promptId}`}>
          {status === "initialize"
            ? `${chatTrans("requesting")}...`
            : status === "processing"
            ? `${chatTrans("progress")}: ${pollProcess.toFixed(2)}%`
            : `${chatTrans("mediaPollingError")}`}
        </Shimmer>
      )}
      {abort && <span>{globalTrans("aborted")}</span>}
    </>
  );
}
