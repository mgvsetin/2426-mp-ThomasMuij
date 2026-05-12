import {
  UnexpectedError,
  UnauthorizedRedirectError,
  ForbiddenError,
  EventNotSelectedError,
  EventNotFoundError,
  MissingEventIdError,
  BoothNotSelectedError,
  InvalidBoothTypeError,
} from '../../cashier_app/static/scripts/general/errors.js';

describe('Custom Error Classes', () => {

  test('UnexpectedError', () => {
    const e = new UnexpectedError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('UnexpectedError');
    expect(e.message).toBe('unexpected_error');
  });

  test('UnexpectedError with custom message', () => {
    const e = new UnexpectedError('custom msg');
    expect(e.message).toBe('custom msg');
  });

  test('UnauthorizedRedirectError', () => {
    const url = '/auth/login';
    const e = new UnauthorizedRedirectError(url);
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('UnauthorizedRedirectError');
    expect(e.message).toBe('unauthorized');
    expect(e.redirectUrl).toBe(url);
  });

  test('ForbiddenError', () => {
    const e = new ForbiddenError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('ForbiddenError');
    expect(e.message).toBe('insufficient_privileges');
  });

  test('EventNotSelectedError', () => {
    const e = new EventNotSelectedError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('EventNotSelectedError');
    expect(e.message).toBe('event_not_selected');
  });

  test('EventNotFoundError', () => {
    const e = new EventNotFoundError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('EventNotFoundError');
    expect(e.message).toBe('event_not_found');
  });

  test('MissingEventIdError', () => {
    const e = new MissingEventIdError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('MissingEventIdError');
    expect(e.message).toBe('missing_event_id');
  });

  test('BoothNotSelectedError', () => {
    const e = new BoothNotSelectedError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('BoothNotSelectedError');
    expect(e.message).toBe('booth_not_selected');
  });

  test('InvalidBoothTypeError', () => {
    const e = new InvalidBoothTypeError();
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('InvalidBoothTypeError');
    expect(e.message).toBe('invalid_booth_type');
  });

  test('all are catchable as Error', () => {
    const errors = [
      new UnexpectedError(),
      new UnauthorizedRedirectError('/login'),
      new ForbiddenError(),
      new EventNotSelectedError(),
      new EventNotFoundError(),
      new MissingEventIdError(),
      new BoothNotSelectedError(),
      new InvalidBoothTypeError(),
    ];
    for (const err of errors) {
      expect(() => { throw err; }).toThrow(Error);
    }
  });
});
