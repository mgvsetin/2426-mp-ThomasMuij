import { UnexpectedError } from "./errors.js";

export async function getSessionInfo() {
  const response = await fetch('/api/session');

  if (!response.ok) {
    throw new UnexpectedError;
  }

  const data = await response.json();

  return data
}
