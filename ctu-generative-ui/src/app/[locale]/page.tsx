"use client";

import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputAttachment,
  PromptInputAttachments,
  PromptInputBody,
  type PromptInputMessage,
  PromptInputTextarea,
  PromptInputSubmit,
  PromptInputToolbar,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
  PromptInputTools,
  PromptInputButton,
} from "@/components/ai-elements/prompt-input";
import { Action, Actions } from "@/components/ai-elements/actions";
import { Fragment, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import {
  ClapperboardIcon,
  CopyIcon,
  DownloadIcon,
  ImageIcon,
  ImagePlusIcon,
  RefreshCcwIcon,
  Settings2Icon,
  XIcon,
} from "lucide-react";
import { Loader } from "@/components/ai-elements/loader";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  cn,
  humanFileSize,
  readFileAsDataURL,
  triggerBrowserDownload,
} from "@/lib/utils";
import { ChatMessage, SupportedAction, SupportedModel } from "@/lib/type";
import TemplateDialog from "./_components/template-dialog";
import { FileUIPart, ReasoningUIPart, RetryError } from "ai";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PollingMedia } from "./_components/polling-media";
import { nanoid } from "nanoid";
import { getPublicAsset } from "@/lib/client/data";
import { AppVersion } from "@/lib/constants";
import ReactPlayer from "react-player";
import TypographyLead from "@/components/ui/typography.lead";
import ChatSuggestions from "@/components/chat-suggestions";
import { Response } from "@/components/ai-elements/response";
import { Image } from "@/components/ai-elements/image";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import { Shimmer } from "@/components/ai-elements/shimmer";

const fileConfig = {
  accept: ".png,.jpg,.jpeg",
  multiple: true,
  maxFileSize: 15 * 1024 * 1024, // 5 MB
  maxFiles: 3,
};

const MAX_TEXT_INPUT_LENGTH = 6000;

function normalizeUIParts(
  parts: Readonly<ChatMessage["parts"]>,
  isStreaming: Readonly<boolean>,
) {
  // Filter out all empty text message parts.
  let newParts = parts.filter((part) => {
    if (part.type === "text") return part.text.trim().length !== 0; // filter out all empty text message parts
    return true;
  });

  // Combine all reasoning parts to the first one.
  const firstReasoningPartIdx = newParts.findIndex(
    (part) => part.type === "reasoning",
  );
  if (firstReasoningPartIdx !== -1) {
    const combinedReasoningPart = newParts
      .filter((part) => part.type === "reasoning")
      .reduce(
        (pre, curr) => ({
          ...pre,
          text: `${pre.text} ${curr.text}`,
          state: isStreaming ? "streaming" : "done",
        }),
        {
          text: "",
          type: "reasoning",
        } as ReasoningUIPart,
      );
    const exclReasoningParts = newParts.filter(
      (part) => part.type !== "reasoning",
    );

    newParts = [
      ...exclReasoningParts.slice(0, firstReasoningPartIdx),
      combinedReasoningPart,
      ...exclReasoningParts.slice(firstReasoningPartIdx),
    ];
  }

  return newParts;
}

const Chat = () => {
  const chatTrans = useTranslations("Chat");
  const appTrans = useTranslations("App");
  const globalTrans = useTranslations("Global");

  const [action, setAction] = useState<SupportedAction>("writing");
  const [input, setInput] = useState("");
  const {
    messages,
    sendMessage,
    setMessages,
    status,
    regenerate,
    stop,
    clearError,
  } = useChat<ChatMessage>({
    onFinish: ({ message }) => {
      setMessages((pre) =>
        pre.map((msg) => {
          if (msg.id !== message.id || msg.role !== "assistant") return msg;
          const newParts = normalizeUIParts(msg.parts, false);
          return { ...msg, parts: newParts };
        }),
      );
    },
    onError: (error) => {
      console.error(error);
      if (RetryError.isInstance(error))
        toast(globalTrans("serviceUnavailable"));
      else toast(globalTrans("unknownError"));
      stop().then(() => clearError());
    },
  });

  const combinedStatus = useMemo<typeof status>(() => {
    const promptQueued = messages.find(
      (msg) =>
        msg.metadata?.type === "generate-media" &&
        msg.metadata?.status === "queued",
    );
    if (promptQueued) return "streaming";
    return status;
  }, [status, messages]);

  const [openTemplateDialog, setOpenTemplateDialog] = useState(false);
  const handleTemplateClick = () => {
    setInput((pre) => `${chatTrans("preprompImageEdit")}. ${pre}`);
    setOpenTemplateDialog(false);
    setAction("generate_image");
  };

  const handleSubmit = async (message: PromptInputMessage) => {
    if (combinedStatus === "streaming" && status !== "streaming") {
      const abortPollingMedia = () => {
        setMessages((currMessages) => {
          const promptQueuedIdx = currMessages.findIndex(
            (msg) =>
              msg.metadata?.type === "generate-media" &&
              msg.metadata?.status === "queued",
          );
          if (promptQueuedIdx === -1) return currMessages;

          const promptQueuedMsg = currMessages[promptQueuedIdx];
          const leftMsgs = currMessages.slice(0, promptQueuedIdx);
          const rightMsgs = currMessages.slice(promptQueuedIdx + 1);
          return [
            ...leftMsgs,
            {
              ...promptQueuedMsg,
              metadata: {
                ...promptQueuedMsg.metadata,
                type: "generate-media",
                status: "aborted",
              },
            },
            ...rightMsgs,
          ];
        });
      };
      abortPollingMedia();
      return;
    }
    if (status === "submitted" || status === "streaming") {
      await stop(); // Stop the streaming
      return;
    }

    const hasText = Boolean(message.text);
    const hasAttachments = Boolean(message.files?.length);
    if (!(hasText || hasAttachments)) return;

    try {
      const files =
        message.files &&
        (await Promise.all(
          message.files.map(async (part) => {
            const blob = await getPublicAsset(part.url);
            const url = await readFileAsDataURL(blob);
            return { ...part, url } as FileUIPart;
          }),
        ));

      sendMessage(
        {
          text: message.text || chatTrans("defaultInput"),
          files: files,
          metadata: { type: "chat" },
        },
        {
          body: {
            action,
            model: "ctu" as SupportedModel,
          },
        },
      );

      setInput("");
    } catch (err) {
      console.error(err);
      toast(globalTrans("unknownError"));
    }
  };

  return (
    <div className="w-full h-screen max-w-4xl py-1 mx-auto p-6 relative">
      <div className="flex flex-col h-full pt-10">
        <Conversation
          className={`${
            messages.length === 0 ? "overflow-y-hidden" : "h-full"
          }`}
        >
          {messages.length === 0 && (
            <ConversationEmptyState
              title={appTrans("name")}
              description={appTrans("description", { version: AppVersion })}
              icon={
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  alt={appTrans("altLogo")}
                  src={"/app_logo.png"}
                  width={150}
                  height={"auto"}
                />
              }
            />
          )}

          <ConversationContent>
            {messages.map((message, idx) => {
              const parts =
                status === "streaming" && message.role === "assistant"
                  ? normalizeUIParts(message.parts, true)
                  : message.parts; // only normalize assistant msgs while streaming
              // const parts = message.parts;

              return (
                <div key={message.id}>
                  {/* {message.role === "assistant" &&
                    parts.filter((part) => part.type === "source-url").length >
                      0 && (
                      <Sources>
                        <SourcesTrigger
                          count={
                            parts.filter((part) => part.type === "source-url")
                              .length
                          }
                        />
                        {parts
                          .filter((part) => part.type === "source-url")
                          .map((part, i) => (
                            <SourcesContent key={`${message.id}-${i}`}>
                              <Source
                                key={`${message.id}-${i}`}
                                href={part.url}
                                title={part.url}
                              />
                            </SourcesContent>
                          ))}
                      </Sources>
                    )} */}

                  {parts.map((part, i) => {
                    switch (part.type) {
                      case "text":
                        return (
                          <Fragment key={`${message.id}-${i}`}>
                            <Message from={message.role}>
                              <MessageContent>
                                <Response>{part.text}</Response>
                                {message.metadata?.type ===
                                  "select-template" && (
                                  <Badge
                                    className="bg-background"
                                    variant={"outline"}
                                    title={message.metadata.template.name}
                                  >
                                    <span className="truncate max-w-[150px] md:max-w-[250px] text-primary">
                                      {`${globalTrans("template")}: ${
                                        message.metadata.template.name
                                      }`}
                                    </span>
                                  </Badge>
                                )}
                              </MessageContent>
                            </Message>
                            {message.role === "assistant" &&
                            message.metadata?.type === "chat" ? (
                              <Actions>
                                <Action
                                  onClick={() =>
                                    regenerate({
                                      messageId: message.id,
                                      metadata: message.metadata,
                                      body: {
                                        action: "writing",
                                        model: "ctu" as SupportedModel,
                                      },
                                    })
                                  }
                                  label={chatTrans("retry")}
                                  tooltip={chatTrans("retry")}
                                >
                                  <RefreshCcwIcon className="size-3" />
                                </Action>
                                <Action
                                  onClick={() =>
                                    navigator.clipboard.writeText(part.text)
                                  }
                                  label={chatTrans("copy")}
                                  tooltip={chatTrans("copy")}
                                >
                                  <CopyIcon className="size-3" />
                                </Action>
                              </Actions>
                            ) : (
                              message.role === "user" && (
                                <Actions className="justify-end">
                                  <Action
                                    onClick={() => {
                                      // const imgParts = parts
                                      //   .filter(
                                      //     (p) =>
                                      //       p.type === "file" &&
                                      //       p.mediaType.includes("image/"),
                                      //   )
                                      //   .map((p) => {
                                      //     const filePart = p as FileUIPart;
                                      //     return new ClipboardItem({
                                      //       [filePart.mediaType]: filePart.url,
                                      //     });
                                      //   });

                                      // navigator.clipboard.write([
                                      //   ...imgParts,
                                      //   new ClipboardItem({
                                      //     "text/plain": part.text,
                                      //   }),
                                      // ]);
                                      navigator.clipboard.writeText(part.text);
                                    }}
                                    label={chatTrans("copy")}
                                    tooltip={chatTrans("copy")}
                                  >
                                    <CopyIcon className="size-3" />
                                  </Action>
                                </Actions>
                              )
                            )}
                          </Fragment>
                        );
                      case "reasoning":
                        return (
                          <Reasoning
                            key={`${message.id}-${i}`}
                            className="w-full"
                            isStreaming={
                              status === "streaming" &&
                              i === parts.length - 1 &&
                              message.id === messages.at(-1)?.id
                            }
                            defaultOpen={false}
                          >
                            <ReasoningTrigger
                              getThinkingMessage={(
                                isStreaming: boolean,
                                duration?: number,
                              ) => {
                                if (isStreaming || duration === 0) {
                                  return (
                                    <Shimmer duration={1}>
                                      {`${chatTrans("thinking")}...`}
                                    </Shimmer>
                                  );
                                }
                                if (duration === undefined) {
                                  return (
                                    <p>{chatTrans("thoughtForFewSeconds")}</p>
                                  );
                                }
                                return (
                                  <p>
                                    {chatTrans("thoughtForSeconds", {
                                      duration: duration ?? 0,
                                    })}
                                  </p>
                                );
                              }}
                            />
                            <ReasoningContent>{part.text}</ReasoningContent>
                          </Reasoning>
                        );
                      case "file":
                        if (
                          !["image/", "video/"].some((type) =>
                            part.mediaType.includes(type),
                          )
                        )
                          return null;
                        return (
                          <Fragment key={`${message.id}-${i}`}>
                            <Message from={message.role}>
                              {part.mediaType.includes("image/") ? (
                                <Image
                                  url={part.url}
                                  alt="The generated image"
                                  className="max-w-1/2 h-auto object-scale-down border"
                                />
                              ) : (
                                <ReactPlayer
                                  controls
                                  crossOrigin={"anonymous"}
                                  src={part.url}
                                  style={{
                                    width: "75%",
                                    height: "auto",
                                    aspectRatio: "16/9",
                                  }}
                                />
                              )}
                            </Message>

                            {message.role === "assistant" && (
                              <Actions>
                                <Action
                                  onClick={() =>
                                    triggerBrowserDownload(part.url)
                                  }
                                  label={chatTrans("download")}
                                  tooltip={chatTrans("download")}
                                >
                                  <DownloadIcon className="size-3" />
                                </Action>
                              </Actions>
                            )}
                          </Fragment>
                        );
                      default:
                        return null;
                    }
                  })}

                  {message.metadata?.type === "generate-media" &&
                    message.metadata.data && (
                      <PollingMedia
                        {...message.metadata.data}
                        abort={message.metadata.status === "aborted"}
                        onMediaSuccess={(data) => {
                          setMessages((messages) => {
                            const leftMsgs = messages.slice(0, idx);
                            const rightMsgs = messages.slice(idx + 1);

                            return [
                              ...leftMsgs,
                              {
                                ...message,
                                metadata: {
                                  ...message.metadata,
                                  type: "generate-media",
                                  status: "finished",
                                },
                              },
                              {
                                id: nanoid(),
                                role: "assistant",
                                parts: [
                                  {
                                    type: "file",
                                    mediaType: data.mimeType,
                                    url: data.url,
                                  },
                                ],
                              },
                              ...rightMsgs,
                            ];
                          });
                        }}
                      />
                    )}
                </div>
              );
            })}

            {(status === "submitted" || status === "streaming") && (
              <Loader title={globalTrans("loading")} />
            )}
          </ConversationContent>

          <ConversationScrollButton />
        </Conversation>

        <PromptInput
          onSubmit={handleSubmit}
          className="mt-4"
          globalDrop
          syncHiddenInput
          {...fileConfig}
          onError={(err) => {
            const error = err as {
              code: "max_files" | "max_file_size" | "accept";
              message: string;
            };
            switch (error.code) {
              case "max_files":
                toast(globalTrans("maxFiles", { max: fileConfig.maxFiles }));
                break;
              case "max_file_size":
                toast(
                  globalTrans("maxFileSize", {
                    size: humanFileSize(fileConfig.maxFileSize),
                  }),
                );
                break;
            }
          }}
        >
          <TemplateDialog
            open={openTemplateDialog}
            onClose={() => setOpenTemplateDialog(false)}
            onTemplateClick={handleTemplateClick}
          />

          <PromptInputBody>
            <ChatSuggestions
              onSuggestionClick={(data) => {
                switch (data.type) {
                  case "text": {
                    setInput(data.text);
                    break;
                  }
                  case "image-template": {
                    setInput(
                      (pre) => `${chatTrans("preprompImageEdit")}. ${pre}`,
                    );
                    setAction("generate_image");
                    break;
                  }
                  default:
                    break;
                }
              }}
            />

            <PromptInputAttachments>
              {(attachment, index) => (
                <div className="flex flex-col items-center">
                  <PromptInputAttachment data={attachment} />
                  <span className="text-center text-muted-foreground font-semibold text-xs">
                    {`${globalTrans("image")} ${index + 1}`}
                  </span>
                </div>
              )}
            </PromptInputAttachments>

            <PromptInputTextarea
              maxLength={MAX_TEXT_INPUT_LENGTH}
              onChange={(e) => setInput(e.target.value)}
              value={input}
              placeholder={chatTrans("promptInputPlaceholder")}
            />
          </PromptInputBody>

          <PromptInputToolbar>
            <PromptInputTools>
              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger className="cursor-pointer" />
                <PromptInputActionMenuContent>
                  <PromptInputActionMenuItem
                    className="cursor-pointer"
                    onClick={() => setOpenTemplateDialog(true)}
                  >
                    <ImagePlusIcon className="mr-2 size-4" />
                    {chatTrans("selectTemplate")}
                  </PromptInputActionMenuItem>

                  <PromptInputActionAddAttachments
                    className="cursor-pointer"
                    label={chatTrans("addAttachments")}
                  />
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>

              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger className="cursor-pointer">
                  <Settings2Icon size={4} />
                </PromptInputActionMenuTrigger>
                <PromptInputActionMenuContent>
                  <PromptInputActionMenuItem
                    className="cursor-pointer"
                    onClick={() => setAction("generate_image")}
                  >
                    <ImageIcon className="mr-2 size-4" />
                    {chatTrans("generateImage")}
                  </PromptInputActionMenuItem>

                  <PromptInputActionMenuItem
                    className="cursor-pointer"
                    onClick={() => setAction("generate_video")}
                  >
                    <ClapperboardIcon className="mr-2 size-4" />
                    {chatTrans("generateVideo")}
                  </PromptInputActionMenuItem>
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>

              <PromptInputButton
                variant={"default"}
                className={cn(
                  "cursor-pointer",
                  action === "generate_image" ? "" : "hidden",
                )}
                onClick={() => setAction("writing")}
              >
                <ImageIcon size={16} />
                <span>{chatTrans("generateImage")}</span>
                <XIcon />
              </PromptInputButton>

              <PromptInputButton
                variant={"default"}
                className={cn(
                  "cursor-pointer",
                  action === "generate_video" ? "" : "hidden",
                )}
                onClick={() => setAction("writing")}
              >
                <ClapperboardIcon size={16} />
                <span>{chatTrans("generateVideo")}</span>
                <XIcon />
              </PromptInputButton>
            </PromptInputTools>
            <Tooltip>
              <TooltipTrigger asChild>
                <PromptInputSubmit
                  disabled={!input && combinedStatus === "ready"}
                  status={combinedStatus}
                />
              </TooltipTrigger>
              <TooltipContent>
                <span>{chatTrans("send")}</span>
              </TooltipContent>
            </Tooltip>
          </PromptInputToolbar>
        </PromptInput>

        <TypographyLead className="p-1 text-center text-sm font-light">
          {chatTrans("contentWarning")}
        </TypographyLead>
      </div>
    </div>
  );
};

export default Chat;
