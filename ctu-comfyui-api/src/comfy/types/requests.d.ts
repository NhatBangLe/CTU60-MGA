declare interface ComfyPromptQueuingRequest {
  prompt: ComfyPrompt;
  extra_data: Record<string, unknown> | null;
}

declare interface ComfyPromptInterruptingRequest {
  prompt_id: string;
}
