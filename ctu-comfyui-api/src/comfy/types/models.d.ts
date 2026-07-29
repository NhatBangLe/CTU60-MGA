declare interface ComfyNode {
  inputs: Record<string, unknown>;
  class_type: string;
  _meta: object;
}

declare type ComfyPrompt = Record<string, ComfyNode>;
