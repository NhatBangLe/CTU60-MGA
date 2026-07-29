declare interface QueuePromptResponse {
  number: number;
  node_errors: unknown;
  prompt_id: string;
}

declare type ComfyResponseType =
  | 'status'
  | 'execution_start'
  | 'execution_cached'
  | 'progress_state'
  | 'executing'
  | 'progress'
  | 'executed'
  | 'execution_error'
  | 'execution_interrupted';

declare interface ComfyResponse {
  type: ComfyResponseType;
  data: unknown;
}

declare interface ComfyStatusResponse extends ComfyResponse {
  type: 'status';
  data: {
    sid?: string;
    status: {
      exec_info: {
        queue_remaining: number;
      };
    };
  };
}

declare interface ComfyExecutionStartResponse extends ComfyResponse {
  type: 'execution_start';
  data: {
    prompt_id: string;
    timestamp: number;
  };
}

declare interface ComfyExecutionCachedResponse extends ComfyResponse {
  type: 'execution_cached';
  data: {
    nodes: unknown[];
    prompt_id: string;
    timestamp: number;
  };
}

declare interface ComfyProgressStateResponse extends ComfyResponse {
  type: 'progress_state';
  data: {
    nodes: unknown;
    prompt_id: string;
  };
}

declare interface ComfyExecutingResponse extends ComfyResponse {
  type: 'executing';
  data: {
    display_node: string;
    node: string;
    prompt_id: string;
  };
}

declare interface ComfyProgressResponse extends ComfyResponse {
  type: 'progress';
  data: {
    max: number;
    value: number;
    node: string;
    prompt_id: string;
  };
}

declare interface ComfyExecutedResponse extends ComfyResponse {
  type: 'executed';
  data: {
    display_node: string;
    node: string;
    output: {
      images: { filename: string; subfolder: string; type: 'output' }[];
    };
    prompt_id: string;
  };
}

declare interface ComfyExecutionErrorResponse extends ComfyResponse {
  type: 'execution_error';
  prompt_id: string;
}

declare interface ComfyExecutionInterruptedResponse extends ComfyResponse {
  type: 'execution_interrupted';
  prompt_id: string;
  node_id: string;
  node_type: string;
  executed: unknown[];
}
