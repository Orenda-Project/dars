/**
 * Dashboard session helpers.
 *
 * The dashboard authenticates with an opaque admin-session token stored under
 * `dars_admin_session` (see lib/dars-api.ts `setAdminSession`). Everyone who
 * logs into /dashboard is an admin, so "is admin" == "has an admin session".
 *
 * Historical note: an earlier PEF-era model stored a `dars_pef_session` JSON
 * blob with an `is_admin` flag and an `api_key`. That key is dead — the real
 * login writes `dars_admin_session`, and the teacher app reads its org key via
 * `getApiKey` in lib/dars-api.ts (`dars_org_api_key`). This module no longer
 * touches `dars_pef_session`.
 */
import { getAdminSession } from "@/lib/dars-api";

export function isAdmin(): boolean {
  return getAdminSession() !== "";
}
