import { EnvVar } from './env.interface';

export default () => {
  const comfyUrl = process.env.COMFY_URL ?? '';
  if (!URL.canParse(comfyUrl)) throw new Error('No valid ComfyUI URL.');
  let clientId = process.env.CLIENT_ID;
  if (!clientId || clientId?.trim().length === 0)
    clientId = crypto.randomUUID();

  return {
    baseUrl: process.env.BASE_URL ?? 'http://127.0.0.1:8080/api/v1',
    comfyui: {
      clientId,
      url: comfyUrl,
      wsInterval: Math.max(
        parseInt(process.env.WS_RECONNECT_INTERVAL_MS ?? '1000', 10),
        0,
      ),
    },
  } as EnvVar;
};
