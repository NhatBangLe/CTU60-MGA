import { Injectable } from '@nestjs/common';
import { ComfyPromptResponse } from './dto/comfy-prompt.response';

@Injectable()
export class ComfyMapper {
  mapPromptToDto(data: ComfyPromptResult): ComfyPromptResponse {
    return {
      promptId: data.promptId,
      progress: data.progress,
      status: data.status,
      file: data.resultFile,
    };
  }
}
