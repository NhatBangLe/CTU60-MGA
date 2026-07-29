import { Inject, Injectable, Logger } from '@nestjs/common';
import { ComfyCacheService } from '../comfy-cache/cache.service';
import StorageService from '../storage/services';
import { WebSocket } from 'ws';
import { ComfyService } from '../comfy/comfy.service';
import mime from 'mime-types';
import { ConfigService } from '@nestjs/config';
import { EnvVar } from '../config/env.interface';

@Injectable()
export class WebSocketService {
  private socket: WebSocket | null = null;
  private totalReconnectAttempts = 0;
  private readonly reconnectIntervalMs: number;
  private readonly logger = new Logger(WebSocketService.name, {
    timestamp: true,
  });
  private readonly clientId: string;

  constructor(
    private readonly configService: ConfigService<EnvVar>,
    private readonly cacheService: ComfyCacheService,
    private readonly comfyService: ComfyService,
    @Inject(StorageService) private readonly storageService: StorageService,
  ) {
    this.clientId = configService.getOrThrow('comfyui.clientId', {
      infer: true,
    });
    this.reconnectIntervalMs = configService.getOrThrow('comfyui.wsInterval', {
      infer: true,
    });
    this.connect();
  }

  private connect() {
    const rawComfyUrl = this.configService.getOrThrow('comfyui.url', {
      infer: true,
    });
    const comfyUrl = new URL(rawComfyUrl);

    if (this.socket !== null) {
      this.socket.removeAllListeners();
      this.socket = null;
    }
    this.socket = new WebSocket(
      `${comfyUrl.protocol === 'https:' ? 'wss' : 'ws'}://${comfyUrl.host}/ws?clientId=${this.clientId}`,
    );
    this.prepareSystemSubscribers(this.socket);
    this.prepareComfyEventSubscribers(this.socket);
  }

  private reconnect() {
    this.logger.log(
      `Attempt #${this.totalReconnectAttempts}: Reconnect will be attempted in ${this.reconnectIntervalMs / 1000} second(s)...`,
    );

    setTimeout(() => {
      this.connect();
      this.totalReconnectAttempts += 1;
    }, this.reconnectIntervalMs);
  }

  private onExecutionError(response: ComfyExecutionErrorResponse) {
    const promptId = response.prompt_id;
    this.logger.error(`Execution error for prompt ID: ${promptId}`);

    this.cacheService
      .getPrompt(promptId)
      .then((prompt) => {
        if (!prompt) return;

        this.cacheService
          .setPrompt(prompt.promptId, { ...prompt, status: 'failed' })
          .catch((err) => this.logger.error(err));
      })
      .catch((err) => this.logger.error(err));
  }

  private onExecutionInterrupted(response: ComfyExecutionInterruptedResponse) {
    const promptId = response.prompt_id;
    this.logger.error(`Execution interrupted for prompt ID: ${promptId}`);

    this.cacheService
      .getPrompt(promptId)
      .then((prompt) => {
        if (!prompt) return;

        this.cacheService
          .setPrompt(prompt.promptId, { ...prompt, status: 'interrupted' })
          .catch((err) => this.logger.error(err));
      })
      .catch((err) => this.logger.error(err));
  }

  private onProgress(response: ComfyProgressResponse) {
    const promptId = response.data.prompt_id;
    this.cacheService
      .getPrompt(promptId)
      .then((prompt) => {
        if (!prompt) return;

        this.cacheService
          .setPrompt(promptId, {
            ...prompt,
            status: 'processing',
            progress:
              (Math.max(response.data.value, 0) /
                Math.max(response.data.max, 1)) *
              100,
          })
          .catch((err) => this.logger.error(err));
      })
      .catch((err) => this.logger.error(err));
  }

  private onExecutionSuccess(response: ComfyExecutedResponse) {
    this.logger.log(
      `Prompt ${response.data.prompt_id} executed successfully at ${new Date().toISOString()}`,
    );
    const images = response.data.output.images;
    if (images.length === 0) {
      return;
    }

    const image = images[0];
    this.comfyService
      .getImage(image)
      .then(async (buffer) => {
        const mimeType = mime.lookup(image.filename);
        const metadata = await this.storageService.saveFile(
          {
            filename: image.filename,
            mimeType: mimeType === false ? undefined : mimeType,
          },
          buffer,
        );
        if (metadata === null) return;

        this.logger.log(
          `Saved file ${metadata.filename} with id ${metadata.id}`,
        );

        await this.cacheService.setPrompt(response.data.prompt_id, {
          progress: 100,
          status: 'completed',
          promptId: response.data.prompt_id,
          resultFile: {
            url: metadata.url,
            mimeType: metadata.mimeType,
          },
        });
      })
      .catch(async (err) => {
        this.logger.error(err);
        await this.cacheService.setPrompt(response.data.prompt_id, {
          progress: 100,
          status: 'failed',
          promptId: response.data.prompt_id,
        });
      });
  }

  private prepareComfyEventSubscribers(socket: WebSocket) {
    socket.on('message', (rawData, isBinary) => {
      if (isBinary) {
        this.logger.warn(`Received a binary message`);
        return;
      }

      const data = rawData.valueOf();
      if (!(data instanceof Buffer)) {
        this.logger.log(`Received an object`);
        return;
      }

      const rawResponse = JSON.parse(data.toString('utf-8')) as ComfyResponse;
      this.logger.debug(JSON.stringify(rawResponse));
      switch (rawResponse.type) {
        case 'execution_error': {
          this.onExecutionError(rawResponse as ComfyExecutionErrorResponse);
          break;
        }
        case 'execution_interrupted': {
          this.onExecutionInterrupted(
            rawResponse as ComfyExecutionInterruptedResponse,
          );
          break;
        }
        case 'progress': {
          this.onProgress(rawResponse as ComfyProgressResponse);
          break;
        }
        case 'executed': {
          this.onExecutionSuccess(rawResponse as ComfyExecutedResponse);
          break;
        }
        default:
          break;
      }
    });
  }

  private prepareSystemSubscribers(socket: WebSocket) {
    socket.on('open', () => {
      this.logger.log('Connected to ComfyUI WebSocket server.');
    });

    socket.on('close', (code, reason) => {
      this.logger.log(
        `Disconnected from ComfyUI WebSocket server with ${code} code.\nReason: ${reason.toString()}.`,
      );
      this.reconnect();
    });
    socket.on('error', (error) => {
      this.logger.error(error.message);
      socket.close(1002, 'Close due to error event.');
    });
  }
}
