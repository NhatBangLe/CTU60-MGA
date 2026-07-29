import { Module } from '@nestjs/common';
import { WebSocketService } from './websocket.service';
import { ComfyCacheModule } from '../comfy-cache/cache.module';
import { StorageModule } from '../storage/storage.module';
import { ComfyModule } from '../comfy/comfy.module';

@Module({
  imports: [ComfyCacheModule, ComfyModule, StorageModule],
  providers: [WebSocketService],
})
export class WebSocketModule {}
