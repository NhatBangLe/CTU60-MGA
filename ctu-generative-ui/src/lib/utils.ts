import { clsx, type ClassValue } from "clsx";
import { nanoid } from "nanoid";
import { twMerge } from "tailwind-merge";
import { FetchError } from "./errors";

export function cn(...inputs: ClassValue[]) {
  "use client";
  return twMerge(clsx(inputs));
}

/**
 * Format bytes as human-readable text.
 *
 * @param bytes Number of bytes.
 * @param si True to use metric (SI) units, aka powers of 1000. False to use
 *           binary (IEC), aka powers of 1024.
 * @param dp Number of decimal places to display.
 *
 * @return Formatted string.
 */
export function humanFileSize(bytes: number, si = false, dp = 1) {
  const thresh = si ? 1000 : 1024;

  if (Math.abs(bytes) < thresh) {
    return bytes + " B";
  }

  const units = si
    ? ["kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    : ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"];
  let u = -1;
  const r = 10 ** dp;

  do {
    bytes /= thresh;
    ++u;
  } while (
    Math.round(Math.abs(bytes) * r) / r >= thresh &&
    u < units.length - 1
  );

  return bytes.toFixed(dp) + " " + units[u];
}

/**
 * This method utilizes an exist URL from a Blob object. Note: This method is not revoke the URL.
 * @param url
 */
export const triggerBrowserDownload = (url: string) => {
  "use client";
  // Create a temporary link element to trigger the download
  const link = document.createElement("a");

  link.href = url;
  link.setAttribute("download", `generated-${nanoid()}.png`); // Set the default file name

  // Append link to the body, click it, and then remove it
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
};

/**
 * Reads a File or Blob and converts it to a Base64 data URL.
 * @param file The file or blob to read.
 * @returns  A promise that resolves with the data URL.
 */
export function readFileAsDataURL(file: Blob): Promise<string> {
  "use client";
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.addEventListener("load", function () {
      resolve(this.result as string);
    });

    reader.addEventListener("error", function () {
      reject(new Error("Cannot encode to Base64 URL"));
    });

    reader.readAsDataURL(file);
  });
}

export function getDataFromBase64URL(dataUrl: string) {
  const matches = dataUrl.match(/^data:(.+);base64,(.*)$/);
  if (!matches || matches.length !== 3) {
    throw new Error("Invalid base64 URL");
  }
  return {
    mimeType: matches[1],
    data: matches[2],
  };
}

export function getRandomInt(min: number, max: number): number {
  min = Math.ceil(min);
  max = Math.floor(max);
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export function consoleLog(
  level: "info" | "warn" | "debug" | "error",
  message: unknown,
  ...optionalParams: unknown[]
) {
  const printMsg = `${new Date().toISOString()} - ${message}`;
  function print(fn: (message: unknown, ...params: unknown[]) => void) {
    if (optionalParams.length !== 0) fn(printMsg, ...optionalParams);
    else fn(printMsg);
  }

  switch (level) {
    case "info":
      print(console.info);
      break;
    case "warn":
      print(console.warn);
      break;
    case "error":
      print(console.error);
      break;
    case "debug":
      print(console.debug);
      break;
  }
}

export async function getFetchError(response: Response) {
  return {
    status: response.status,
    statusText: response.statusText,
    message: await response.text(),
  } as FetchError;
}

export function isValidWebURL(url: URL | string) {
  if (!URL.canParse(url)) return false;
  const input = new URL(url);

  return input.protocol === "https:" || input.protocol === "http:";
}
