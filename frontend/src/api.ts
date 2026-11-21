let token = '';
export function setToken(value: string) { token = value; }
export async function api<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const form = data instanceof FormData;
  if (data && !form) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, { method, headers, body: data ? (form ? data : JSON.stringify(data)) : undefined });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail || response.statusText));
  }
  return response.json();
}
