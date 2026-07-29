import { Module } from '@nestjs/common';
import LocalStorageService from './services/local.service';
import { StorageController } from './storage.controller';
import { StorageMapper } from './storage.mapper';
import StorageService from './services';

const storageServiceProvider = {
  provide: StorageService,
  useClass: LocalStorageService,
};

@Module({
  providers: [StorageMapper, storageServiceProvider],
  controllers: [StorageController],
  exports: [StorageService],
})
export class StorageModule {}
