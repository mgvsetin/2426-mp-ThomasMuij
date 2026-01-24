export class UnexpectedError extends Error {
  constructor(message = 'unexpected_error') {
    super(message);
    this.name = 'UnexpectedError';
  }
}

export class UnauthorizedRedirectError extends Error {
  constructor(redirectUrl) {
    super('unauthorized');
    this.name = 'UnauthorizedRedirectError';
    this.redirectUrl = redirectUrl;
  }
}

export class ForbiddenError extends Error {
  constructor() {
    super('insufficient_privileges');
    this.name = 'ForbiddenError';
  }
}

export class EventNotSelectedError extends Error {
  constructor() {
    super('event_not_selected');
    this.name = 'EventNotSelectedError';
  }
}

export class EventNotFoundError extends Error {
  constructor() {
    super('event_not_found');
    this.name = 'EventNotFoundError';
  }
}

export class MissingEventIdError extends Error {
  constructor() {
    super('missing_event_id');
    this.name = 'MissingEventIdError';
  }
}

export class BoothNotSelectedError extends Error {
  constructor() {
    super('booth_not_selected');
    this.name = 'BoothNotSelectedError';
  }
}

export class InvalidBoothTypeError extends Error {
  constructor() {
    super('invalid_booth_type');
    this.name = 'InvalidBoothTypeError';
  }
}
