import { ComfyCacheModule } from './comfy-cache/cache.module';
import { Module } from '@nestjs/common';
import { ComfyModule } from './comfy/comfy.module';
import { WebSocketModule } from './ws/websocket.module';
import { ConfigModule } from '@nestjs/config';
import { CacheModule } from '@nestjs/cache-manager';
import { StorageModule } from './storage/storage.module';
import { UtilityModule } from './utils/utility.module';
import { ComfyClientModule } from './comfy-client/client.module';
import configuration from './config/configuration';

@Module({
  imports: [
    CacheModule.register({ isGlobal: true }),
    ConfigModule.forRoot({ isGlobal: true, load: [configuration] }),
    UtilityModule,
    StorageModule,
    ComfyCacheModule,
    ComfyModule,
    WebSocketModule,
    ComfyClientModule,
  ],
})
export class AppModule {}
