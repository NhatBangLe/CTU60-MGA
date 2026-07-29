declare interface ComfyPromptSuccessResponse {
  prompt_id: string;
  number: number;
  node_errors: Record<string, unknown>;
}

declare interface ComfyPromptErrorResponse {
  type:
    | 'no_prompt'
    | 'invalid_prompt'
    | 'prompt_no_outputs'
    | 'exception_during_validation'
    | 'prompt_outputs_failed_validation';
  message: string;
  details: string;
  extra_info: Record<string, unknown>;
}

declare interface ComfyGeneratedMetadataResponse {
  images?: Array<{ filename: string; subfolder: string; type: string }>;
}

declare interface ComfyHistoryResponse {
  outputs: Record<string, ComfyGeneratedMetadataResponse>;
}
