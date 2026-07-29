import { HttpModule } from '@nestjs/axios';
import { Module } from '@nestjs/common';
import { UtilityModule } from '../utils/utility.module';
import { ComfyClient } from './comfy.client';

@Module({
  imports: [
    HttpModule.register({
      timeout: 5000,
      maxRedirects: 5,
    }),
    UtilityModule,
  ],
  providers: [ComfyClient],
  exports: [ComfyClient],
})
export class ComfyClientModule {}
