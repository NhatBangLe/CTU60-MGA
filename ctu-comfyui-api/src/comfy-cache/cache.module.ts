import { Module } from '@nestjs/common';
import { ComfyCacheService } from './cache.service';

@Module({
  providers: [ComfyCacheService],
  exports: [ComfyCacheService],
})
export class ComfyCacheModule {}
