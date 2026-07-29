import { ComfyMapper } from './comfy.mapper';
import { Module } from '@nestjs/common';
import { ComfyController } from './comfy.controller';
import { ComfyService } from './comfy.service';
import { ComfyCacheModule } from '../comfy-cache/cache.module';
import { ComfyClientModule } from '../comfy-client/client.module';

@Module({
  imports: [ComfyCacheModule, ComfyClientModule],
  controllers: [ComfyController],
  providers: [ComfyMapper, ComfyService],
  exports: [ComfyService],
})
export class ComfyModule {}
