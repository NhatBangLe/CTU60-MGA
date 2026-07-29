import { Injectable } from '@nestjs/common';

@Injectable()
export class UtilityService {
  extractBase64URL(base64url: string) {
    const mimeType = base64url.substring(5, base64url.indexOf(';base64,'));
    const data = base64url.substring(base64url.lastIndexOf(';base64,') + 8);
    return { mimeType, data };
  }

  isValidWebURL(url: URL) {
    return ['http:', 'https:'].includes(url.protocol);
  }

  isValidDataURL(url: URL) {
    return url.protocol === 'data:';
  }
}
