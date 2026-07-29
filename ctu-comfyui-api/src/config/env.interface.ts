export interface EnvVar {
  baseUrl?: string;
  comfyui: {
    url: string;
    clientId?: string;
    wsInterval?: number;
  };
}
