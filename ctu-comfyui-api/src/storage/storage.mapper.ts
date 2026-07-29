import { Injectable } from '@nestjs/common';
import { FileMetadata } from './services';
import { FileMetadataResponse } from './dto/file-metadata.response';

@Injectable()
export class StorageMapper {
  mapMetadataToDto(data: FileMetadata): FileMetadataResponse {
    return {
      filename: data.filename,
      id: data.id,
      mimeType: data.mimeType,
      size: data.size,
      url: data.url,
    };
  }
}
