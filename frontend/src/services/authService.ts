import api from '@/services/api';
import { User } from '@/types';

/**
 * Thin wrapper around the auth endpoints not already covered by
 * AuthContext (which owns login/logout directly since they also need to
 * update in-memory state). This file exists so forms/components can share
 * request/response typing without reaching into AuthContext internals.
 */

export interface RegisterPayload {
  email: string;
  password: string;
  full_name?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

/**
 * Registers a new user. Does NOT log the user in — callers (AuthContext's
 * `register`) should follow up with `login()` to obtain tokens and populate
 * the current user.
 */
export async function registerUser(payload: RegisterPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/register', payload);
  return data;
}

/** Fetches the currently authenticated user's profile. */
export async function fetchCurrentUser(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  return data;
}
