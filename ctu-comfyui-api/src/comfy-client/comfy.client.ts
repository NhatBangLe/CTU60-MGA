import {
  Injectable,
  HttpException,
  HttpStatus,
  InternalServerErrorException,
  Logger,
  BadRequestException,
} from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { isAxiosError } from 'axios';
import { URLSearchParams } from 'node:url';
import mime from 'mime-types';
import FormData from 'form-data';
import { Readable } from 'node:stream';
import { UtilityService } from '../utils/utility.service';
import { ConfigService } from '@nestjs/config';
import { EnvVar } from '../config/env.interface';

@Injectable()
export class ComfyClient {
  private readonly comfyUrl: string;
  private readonly clientId: string;
  private readonly logger = new Logger(ComfyClient.name, {
    timestamp: true,
  });

  constructor(
    private readonly configService: ConfigService<EnvVar>,
    private readonly httpService: HttpService,
    private readonly utilityService: UtilityService,
  ) {
    this.clientId = this.configService.getOrThrow('comfyui.clientId', {
      infer: true,
    });
    this.comfyUrl = this.configService.getOrThrow('comfyui.url', {
      infer: true,
    });
  }

  /**
   * Submits a preprocessed workflow to the ComfyUI server's execution queue.
   * @param preprocessedPrompt - The workflow object ready for inference (API format).
   * @returns A promise that resolves to the unique `prompt_id` assigned by the server.
   * @throws `HttpException`
   * Thrown with `HttpStatus.INTERNAL_SERVER_ERROR` (500) if ComfyUI returns
   * 'exception_during_validation' or 'prompt_outputs_failed_validation'.
   * @throws `HttpException`
   * Thrown with `HttpStatus.BAD_REQUEST` (400) for all other ComfyUI validation errors.
   * @throws `InternalServerErrorException`
   * Thrown if the request fails (e.g., network error) or an unexpected error occurs.
   */
  async queuePrompt(preprocessedPrompt: ComfyPrompt) {
    try {
      const { data } = await firstValueFrom(
        this.httpService.post<
          ComfyPromptSuccessResponse,
          ComfyPromptQueuingRequest
        >(
          `${this.comfyUrl}/prompt`,
          {
            prompt: preprocessedPrompt,
            extra_data: {
              client_id: this.clientId,
            },
          },
          {
            headers: {
              'Content-Type': 'application/json',
            },
          },
        ),
      );

      return data.prompt_id;
    } catch (error) {
      if (isAxiosError(error)) {
        const data = error.response?.data as ComfyPromptErrorResponse;
        let status = HttpStatus.BAD_REQUEST;
        switch (data.type) {
          case 'exception_during_validation':
          case 'prompt_outputs_failed_validation':
            status = HttpStatus.INTERNAL_SERVER_ERROR;
            break;
          default:
            break;
        }
        throw new HttpException(data.message, status);
      } else {
        this.logger.error('ComfyUI Error:', error);
        throw new InternalServerErrorException(
          'Failed to communicate with ComfyUI',
        );
      }
    }
  }

  /**
   * Requests the server to stop the execution of a specific prompt.
   * @param promptId - The unique identifier of the prompt to be interrupted.
   * @returns A promise that resolves once the interrupt request has been acknowledged.
   * @throws `HttpException`
   * Thrown if the interrupt request fails. The status code matches the server's response
   * or defaults to `HttpStatus.SERVICE_UNAVAILABLE` (503).
   * @throws `InternalServerErrorException`
   * Thrown if the client cannot communicate with the server or a non-Axios error occurs.
   */
  async interruptPrompt(promptId: string) {
    try {
      await firstValueFrom(
        this.httpService.post<void, ComfyPromptInterruptingRequest>(
          `${this.comfyUrl}/interrupt`,
          { prompt_id: promptId },
          {
            headers: {
              'Content-Type': 'application/json',
            },
          },
        ),
      );
    } catch (error) {
      throw this.getHttpException(error);
    }
  }

  /**
   * Retrieves a generated or uploaded image from the ComfyUI server as a binary buffer.
   * @param query - The location details of the image.
   * @returns A promise that resolves to a Buffer containing the image data.
   * @throws `HttpException`
   * Thrown if ComfyUI returns an error. The status code matches the server's response
   * (e.g., 404 for missing files) or defaults to `HttpStatus.SERVICE_UNAVAILABLE` (503).
   * @throws `InternalServerErrorException`
   * Thrown if the client cannot communicate with the server or a non-Axios error occurs.
   */
  async getImage({
    filename,
    subfolder,
    type,
  }: {
    filename: string;
    subfolder: string;
    type: string;
  }) {
    try {
      const params = new URLSearchParams();
      params.set('filename', filename);
      params.set('subfolder', subfolder);
      params.set('type', type);

      const { data } = await firstValueFrom(
        this.httpService.get<string>(`${this.comfyUrl}/view`, {
          params: params,
          responseType: 'arraybuffer',
        }),
      );
      return Buffer.from(data);
    } catch (error) {
      throw this.getHttpException(error);
    }
  }

  /**
   * Uploads a file (image, video, etc.) to the ComfyUI server for use in workflows.
   * @param data - The file data and destination metadata.
   * @returns A promise that resolves to the server's confirmation including the saved name and path.
   * @throws `HttpException`
   * Thrown if the upload fails. The status code reflects the server's response
   * or defaults to `HttpStatus.SERVICE_UNAVAILABLE` (503).
   * @throws `InternalServerErrorException`
   * Thrown if the client cannot communicate with the server or a non-Axios error occurs.
   */
  async uploadFile({
    file,
    metadata,
    type,
    overwrite = true,
  }: {
    file: Buffer;
    metadata: { filename?: string; mimeType: string; subfolder?: string };
    type: 'input' | 'temp' | 'output';
    overwrite?: boolean;
  }) {
    try {
      const formData = new FormData();
      formData.append('subfolder', metadata.subfolder ?? '');
      formData.append('type', type);
      formData.append('overwrite', `${overwrite}`);
      formData.append('image', Readable.from(file), {
        contentType: metadata.mimeType,
        filename:
          metadata.filename ??
          `${crypto.randomUUID()}.${mime.extension(metadata.mimeType)}`,
      });

      const { data } = await firstValueFrom(
        this.httpService.postForm<{
          name: string;
          subfolder: string;
          type: 'input' | 'temp' | 'output';
        }>(`${this.comfyUrl}/upload/image`, formData),
      );
      return data;
    } catch (error) {
      this.logger.warn(
        `Cannot upload file ${JSON.stringify(metadata)} - type: ${type}.`,
      );
      throw this.getHttpException(error);
    }
  }

  private getHttpException(error: unknown) {
    if (isAxiosError(error)) {
      const responseData = error.response?.data as
        | string
        | Record<string, unknown>;

      return new HttpException(
        responseData,
        error.response?.status ?? HttpStatus.SERVICE_UNAVAILABLE,
      );
    } else {
      this.logger.error('ComfyUI Error:', error);
      return new InternalServerErrorException(
        'Failed to communicate with ComfyUI',
      );
    }
  }

  /**
   * Prepares a raw workflow by applying transformations, such as resolving media inputs
   * from URLs or local paths and validating file types.
   * @param rawPrompt - The initial workflow structure or template.
   * @returns A promise that resolves to the validated and processed `ComfyPrompt` object.
   * @throws `BadRequestException`
   * Thrown if the media input is a URL but is neither a valid Web URL nor a Data URL.
   * @throws `BadRequestException`
   * Thrown if the input is not a recognizable local path (e.g., doesn't start with `/`, `./`, or `../`).
   * @throws `BadRequestException`
   * Thrown if the MIME type of a provided URL cannot be detected.
   */
  async preprocessPrompt(rawPrompt: ComfyPrompt) {
    const mediaInputFolder = 'from_user';
    const mediaKey = 'image';

    const newEntries = await Promise.all(
      Object.entries(rawPrompt).map(async (pair) => {
        const [key, node] = pair;
        if (!Object.hasOwn(node.inputs, mediaKey)) return pair;

        const fileInput = node.inputs[mediaKey] as string;
        let input = '';

        if (URL.canParse(fileInput)) {
          const url = new URL(fileInput);
          if (this.utilityService.isValidDataURL(url))
            input = await this.handleFileFromDataURL(url, mediaInputFolder);
          else if (this.utilityService.isValidWebURL(url))
            input = await this.handleFileFromWebURL(url, mediaInputFolder);
          else
            throw new BadRequestException(
              'Cannot collect media file from provided URL. The URL must be a web URL or data URL.',
            );
        } else if (
          (fileInput.startsWith('/') &&
            fileInput.length < 4096 &&
            !fileInput.endsWith('==')) ||
          fileInput.startsWith('./') ||
          fileInput.startsWith('../')
        ) {
          input = fileInput; // local path
        } else
          throw new BadRequestException(
            'Cannot collect media file. The file input must be one of these types: local path, web URL and data URL.',
          );

        const newNode = {
          ...node,
          inputs: { ...node.inputs, [mediaKey]: input },
        } as ComfyNode;
        return [key, newNode];
      }),
    );

    return Object.fromEntries(newEntries) as ComfyPrompt;
  }

  private async handleFileFromDataURL(url: URL, subfolder?: string) {
    // base64url - data:image/png;base64,iVBORw0KGgoAAAA...
    const { data, mimeType } = this.utilityService.extractBase64URL(
      url.toString(),
    );
    const uploadInputResult = await this.uploadFile({
      file: Buffer.from(data, 'base64'),
      type: 'input',
      metadata: { mimeType, subfolder },
    });
    return `${uploadInputResult?.subfolder}/${uploadInputResult?.name}`;
  }

  private async handleFileFromWebURL(url: URL, subfolder?: string) {
    const urlAsStr = url.toString();

    const { data, headers } = await firstValueFrom(
      this.httpService.get<ArrayBuffer>(urlAsStr, {
        responseType: 'arraybuffer',
      }),
    );
    const buffer = Buffer.from(data);
    const mimeType = headers['content-type'] as string | undefined;
    if (mimeType === undefined || typeof mimeType !== 'string')
      throw new BadRequestException({
        message: 'Cannot detect MIME type of media file from provided URL.',
        url: urlAsStr,
      });

    const uploadInputResult = await this.uploadFile({
      file: buffer,
      type: 'input',
      metadata: { mimeType, subfolder },
    });
    return `${uploadInputResult?.subfolder}/${uploadInputResult?.name}`;
  }
}
