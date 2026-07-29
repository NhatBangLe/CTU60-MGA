import { Injectable } from '@nestjs/common';

export interface FileMetadata {
  id: string;
  filename: string;
  size: number;
  mimeType: string;
  url: string;
}

@Injectable()
export default abstract class StorageService {
  abstract getFile(id: string): Promise<FileMetadata | null>;
  abstract saveFile(
    metadata: Partial<Pick<FileMetadata, 'filename' | 'mimeType'>>,
    data: Buffer,
  ): Promise<FileMetadata | null>;
  abstract deleteFile(id: string): Promise<boolean>;
}
