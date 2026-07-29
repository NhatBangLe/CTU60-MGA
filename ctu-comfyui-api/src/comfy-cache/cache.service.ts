import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { Inject, Injectable } from '@nestjs/common';
import type { Cache } from 'cache-manager';

const DEFAULT_TTL_MS = 3600000; // 1 hour

@Injectable()
export class ComfyCacheService {
  constructor(@Inject(CACHE_MANAGER) private cacheManager: Cache) {}

  async getPrompt(promptId: string) {
    return this.cacheManager.get<ComfyPromptResult | null>(
      this.buildKey(promptId),
    );
  }

  async setPrompt(promptId: string, value: ComfyPromptResult) {
    return this.cacheManager.set(
      this.buildKey(promptId),
      value,
      DEFAULT_TTL_MS,
    );
  }

  private buildKey(id: string) {
    return `prompt:${id}`;
  }
}
