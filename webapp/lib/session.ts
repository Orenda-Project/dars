export interface DarsSession {
  api_key: string;
  client_id?: string;
  name?: string;
  email?: string;
  is_admin?: boolean;
}

export function getSession(): DarsSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export function getApiKey(): string {
  return getSession()?.api_key ?? "";
}

export function isAdmin(): boolean {
  return getSession()?.is_admin === true;
}
