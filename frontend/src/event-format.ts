import type { InstallationEventView } from "./backend";

export function eventTimestampLabel(timestamp: string): string {
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return "время неизвестно";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(date);
}

export function taskNameWithoutRole(
  event: InstallationEventView,
): string | undefined {
  const name = event.task?.name;
  const role = event.task?.role?.trim();
  if (!name || !role || !name.startsWith(role)) return name;

  const remainder = name.slice(role.length);
  const separator = remainder.match(/^\s*:\s*/);
  return separator ? remainder.slice(separator[0].length) || name : name;
}
