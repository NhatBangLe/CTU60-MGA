import {
  Controller,
  Get,
  Param,
  Header,
  NotFoundException,
  ServiceUnavailableException,
  StreamableFile,
  HttpCode,
  Inject,
} from '@nestjs/common';
import StorageService from './services';
import LocalStorageService from './services/local.service';
import { createReadStream } from 'node:fs';
import { StorageMapper } from './storage.mapper';
import { ApiOkResponse } from '@nestjs/swagger';
import { FileMetadataResponse } from './dto/file-metadata.response';
import mime from 'mime-types';

@Controller('files')
export class StorageController {
  constructor(
    @Inject(StorageService) private readonly storageService: StorageService,
    private readonly mapper: StorageMapper,
  ) {}

  @Get(':fileId/metadata')
  @HttpCode(200)
  @Header('Cache-Control', 'public, max-age=604800, immutable')
  @ApiOkResponse({ type: FileMetadataResponse })
  async getFileMetadata(@Param('fileId') fileId: string) {
    const metadata = await this.storageService.getFile(fileId);
    if (metadata === null) throw new NotFoundException('File not found.');
    return this.mapper.mapMetadataToDto(metadata);
  }

  @Get(':fileId/view')
  @HttpCode(200)
  @Header('Cache-Control', 'public, max-age=604800, immutable')
  @ApiOkResponse({ description: 'File stream' })
  async streamFile(@Param('fileId') fileId: string) {
    if (this.storageService instanceof LocalStorageService) {
      const metadata = await this.storageService.getLocalFile(fileId);
      if (metadata === null) throw new NotFoundException('File not found.');

      const readableStream = createReadStream(metadata.path);
      let filename = fileId;
      const ext = mime.extension(metadata.mimeType);
      if (ext !== false) filename = `${filename}.${ext}`;

      return new StreamableFile(readableStream, {
        type: metadata.mimeType,
        length: metadata.size,
        disposition: `attachment; filename="${filename}"`,
      });
    } else
      throw new ServiceUnavailableException(
        'Storage service is not available.',
      );
  }
}
