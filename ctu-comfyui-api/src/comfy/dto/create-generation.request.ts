import { ApiProperty } from '@nestjs/swagger';
import { IsNotEmpty } from 'class-validator';

export class CreateGenerationRequest {
  @IsNotEmpty()
  @ApiProperty({ description: 'ComfyUI API workflow', nullable: false })
  prompt: ComfyPrompt;
}
