import {
  Controller,
  Post,
  Get,
  BadRequestException,
  HttpCode,
  Param,
  type RawBodyRequest,
  Req,
  Logger,
} from '@nestjs/common';
import { ComfyService } from './comfy.service';
import { CreateGenerationRequest } from './dto/create-generation.request';
import { FastifyRequest } from 'fastify';
import { ApiCreatedResponse, ApiOkResponse } from '@nestjs/swagger';
import { ComfyMapper } from './comfy.mapper';
import { ComfyPromptResponse } from './dto/comfy-prompt.response';
import { isJSON } from 'class-validator';

@Controller('comfy')
export class ComfyController {
  private readonly logger = new Logger(ComfyController.name, {
    timestamp: true,
  });
  constructor(
    private readonly comfyService: ComfyService,
    private readonly mapper: ComfyMapper,
  ) {}

  @Post('generate')
  @HttpCode(201)
  @ApiCreatedResponse({
    description: 'Prompt queued',
    type: String,
  })
  async generate(@Req() req: RawBodyRequest<FastifyRequest>) {
    const raw = req.rawBody;
    if (raw === undefined)
      throw new BadRequestException('Missing request body.');
    const rawString = raw.toString('utf-8');
    if (!isJSON(rawString)) throw new BadRequestException('Invalid prompt.');

    const dto = JSON.parse(rawString) as CreateGenerationRequest;
    if (!dto.prompt) throw new BadRequestException('Missing prompt.');

    return this.comfyService.generate(dto.prompt);
  }

  @Get(':promptId/status')
  @HttpCode(200)
  @ApiOkResponse({
    description: 'Prompt status',
    type: ComfyPromptResponse,
  })
  async getStatus(@Param('promptId') promptId: string) {
    if (!promptId) throw new BadRequestException('Missing promptId');
    const prompt = await this.comfyService.checkStatus(promptId);
    return this.mapper.mapPromptToDto(prompt);
  }
}
