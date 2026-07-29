import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class ComfyPromptResponse {
  @ApiProperty()
  promptId: string;
  @ApiProperty()
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'interrupted';
  @ApiProperty({
    description: 'Current progress in percentage',
    example: '0.0',
  })
  progress: number;
  @ApiPropertyOptional({
    description: 'Media file metadata after prompt is completed',
  })
  file?: {
    url: string;
    mimeType: string;
  };
}
