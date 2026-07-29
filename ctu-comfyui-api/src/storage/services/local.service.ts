import { Inject, Logger } from '@nestjs/common';
import StorageService, { FileMetadata } from '.';
import { join } from 'node:path';
import type { Cache } from 'cache-manager';
import { unlink, writeFile } from 'node:fs/promises';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { existsSync, mkdirSync } from 'node:fs';
import { ConfigService } from '@nestjs/config';
import { EnvVar } from '../../config/env.interface';

export interface LocalFileMetadata extends FileMetadata {
  path: string;
}

export default class LocalStorageService extends StorageService {
  private readonly storageDir = join(process.cwd(), 'storage');
  private readonly baseUrl: string;
  private readonly logger = new Logger(LocalStorageService.name, {
    timestamp: true,
  });

  constructor(
    @Inject(CACHE_MANAGER) private readonly cacheManager: Cache,
    private readonly configService: ConfigService<EnvVar>,
  ) {
    super();
    if (!existsSync(this.storageDir)) mkdirSync(this.storageDir);
    this.baseUrl = this.configService.getOrThrow('baseUrl', { infer: true });
  }

  async getLocalFile(id: string): Promise<LocalFileMetadata | null> {
    const metadata = await this.cacheManager.get<LocalFileMetadata>(
      this.getCacheKey(id),
    );
    return metadata === undefined ? null : { ...metadata };
  }

  async getFile(id: string): Promise<FileMetadata | null> {
    return this.getLocalFile(id);
  }

  async saveFile(
    metadata: Partial<Pick<FileMetadata, 'filename' | 'mimeType'>>,
    data: Buffer,
  ): Promise<FileMetadata | null> {
    const fileId = crypto.randomUUID();
    const savePath = join(this.storageDir, fileId);
    const size = data.byteLength;

    try {
      const result: LocalFileMetadata = {
        id: fileId,
        size,
        filename: metadata.filename ?? fileId,
        mimeType: metadata.mimeType ?? 'application/octet-stream',
        url: `${this.baseUrl}/files/${fileId}/view`,
        path: savePath,
      };
      await Promise.all([
        writeFile(savePath, data), // Write the data to the file
        this.cacheManager.set(this.getCacheKey(result.id), result),
      ]);

      return result;
    } catch (error) {
      this.logger.warn(
        `Cannot save file ${metadata.filename} - ${metadata.mimeType}.`,
        error,
      );
      return null;
    }
  }

  async deleteFile(id: string): Promise<boolean> {
    const cacheKey = this.getCacheKey(id);
    const metadata = await this.cacheManager.get<LocalFileMetadata>(cacheKey);
    if (!metadata) return false;

    const filePath = metadata.path;
    try {
      await Promise.all([unlink(filePath), this.cacheManager.del(cacheKey)]);

      return true;
    } catch (error) {
      this.logger.warn(`Cannot delete file at path ${filePath}.`, error);
      return false;
    }
  }

  private getCacheKey(id: string): string {
    return `file-metadata:${id}`;
  }
}
