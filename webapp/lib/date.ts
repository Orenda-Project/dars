/**
 * Date display helpers — always day/month/year (e.g. 20/10/1999), never American M/D/Y.
 *
 * Use these instead of `toLocaleDateString()` without a locale: the bare call inherits
 * the browser/OS locale and renders American M/D on US machines. These pin to numeric
 * en-GB so the format is stable regardless of where the user's machine is configured.
 */

/** Build a local Date from a date-only ISO string ("YYYY-MM-DD"), avoiding TZ drift. */
function fromIsoDate(iso: string): Date | null {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  const dt = new Date(y, m - 1, d);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

/** Date → "20/10/1999" (numeric day/month/year). */
export function formatDMY(date: Date): string {
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** ISO date ("YYYY-MM-DD") → "20/10/1999", or "—" when unset / unparseable. */
export function formatIsoDMY(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = fromIsoDate(iso);
  return dt ? formatDMY(dt) : iso;
}

/** ISO date ("YYYY-MM-DD") → "Mon, 20/10/1999" (short weekday + numeric DMY). */
export function formatIsoWeekdayDMY(iso: string | null | undefined): string {
  if (!iso) return "—";
  const dt = fromIsoDate(iso);
  if (!dt) return iso;
  const weekday = dt.toLocaleDateString("en-GB", { weekday: "short" });
  return `${weekday}, ${formatDMY(dt)}`;
}
