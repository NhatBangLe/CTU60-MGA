declare interface ComfyPromptResult {
  promptId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'interrupted';
  progress: number;
  resultFile?: {
    url: string;
    mimeType: string;
  };
}
