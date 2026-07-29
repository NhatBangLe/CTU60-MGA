import { Injectable, NotFoundException } from '@nestjs/common';
import { ComfyCacheService } from '../comfy-cache/cache.service';
import { ComfyClient } from '../comfy-client/comfy.client';

@Injectable()
export class ComfyService {
  constructor(
    private readonly comfyClient: ComfyClient,
    private readonly cacheService: ComfyCacheService,
  ) {}

  async generate(rawPrompt: ComfyPrompt) {
    const preprocessed = await this.comfyClient.preprocessPrompt(rawPrompt);
    const promptId = await this.comfyClient.queuePrompt(preprocessed);

    // Global cache
    await this.cacheService.setPrompt(promptId, {
      promptId,
      progress: 0,
      status: 'pending',
    });

    return {
      promptId, // ComfyUI's internal ID
    };
  }

  async checkStatus(promptId: string) {
    const prompt = await this.cacheService.getPrompt(promptId);
    if (!prompt) throw new NotFoundException('Prompt not found');
    return prompt;
  }

  getImage(query: { filename: string; subfolder: string; type: string }) {
    return this.comfyClient.getImage(query);
  }

  uploadFile(data: {
    file: Buffer;
    metadata: { filename?: string; mimeType: string; subfolder?: string };
    type: 'input' | 'temp' | 'output';
    overwrite?: boolean;
  }) {
    return this.comfyClient.uploadFile(data);
  }

  interruptPrompt(promptId: string) {
    return this.comfyClient.interruptPrompt(promptId);
  }
}
