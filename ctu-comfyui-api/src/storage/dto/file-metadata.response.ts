import { ApiProperty } from '@nestjs/swagger';

export class FileMetadataResponse {
  @ApiProperty()
  id: string;
  @ApiProperty()
  filename: string;
  @ApiProperty()
  size: number;
  @ApiProperty()
  mimeType: string;
  @ApiProperty()
  url: string;
}
