export type ErrorType = "handling" | "not-found" | "validation" | "unknown";

export class AppError implements Error {
  type: ErrorType;
  name: string;
  message: string;
  cause?: unknown;

  constructor(message?: string, options?: ErrorOptions) {
    this.message = message ?? "";
    this.cause = options?.cause;
    this.type = "unknown";
    this.name = "AppError";
  }
}

export class HandlingError extends AppError {
  constructor(message?: string, options?: ErrorOptions) {
    super(message, options);
    this.type = "handling";
    this.name = "HandlingError";
  }
}

export class NotFoundError extends AppError {
  constructor(message?: string, options?: ErrorOptions) {
    super(message, options);
    this.type = "not-found";
    this.name = "NotFoundError";
  }
}

export class ValidationError extends AppError {
  constructor(message?: string, options?: ErrorOptions) {
    super(message, options);
    this.type = "validation";
    this.name = "ValidationError";
  }
}

export interface FetchError {
  message?: string;
  status: number;
  statusText: string;
}
