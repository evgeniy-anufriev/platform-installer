import type { OpenResult } from "./backend";
export type ObjectValue = Record<string, unknown>;
export type ApplicationIntent = {
  operation:
    | "CreateApplicationLibraryDeployment"
    | "UpdateApplicationLibraryDeployment"
    | "DeleteApplicationLibraryDeployment"
    | "SetApplicationLibrarySlot"
    | "RemoveApplicationLibrarySlot"
    | "SetApplicationLibraryPlacement"
    | "RemoveApplicationLibraryPlacement"
    | "SetApplicationLibraryOverride"
    | "RemoveApplicationLibraryOverride";
  deploymentId: string;
  entityId?: string;
  hostId?: string;
  entity?: ObjectValue;
  placement?: ObjectValue;
  property?: string;
  setting?: string;
  value?: unknown;
};
export const isApplicationIntent = (value: {
  operation: string;
}): value is ApplicationIntent =>
  value.operation.includes("ApplicationLibrary");
export const objectValue = (value: unknown): ObjectValue =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as ObjectValue)
    : {};
// This projects authored edit intents only. No inheritance/resolution is performed.
export function applicationDraft(
  managed: OpenResult["managed"],
  intents: ApplicationIntent[],
) {
  const libraries = Object.assign(
    Object.create(null),
    structuredClone(managed?.applicationLibraries ?? {}),
  ) as Record<string, ObjectValue>;
  const placements = Object.assign(
    Object.create(null),
    structuredClone(managed?.applicationPlacements ?? {}),
  ) as Record<string, ObjectValue>;
  for (const c of intents) {
    const id = c.deploymentId;
    if (c.operation === "CreateApplicationLibraryDeployment")
      libraries[id] = { ...c.entity };
    else if (c.operation === "DeleteApplicationLibraryDeployment")
      delete libraries[id];
    else if (c.operation === "UpdateApplicationLibraryDeployment")
      libraries[id] = { ...libraries[id], ...c.entity };
    else if (c.hostId && c.operation.endsWith("Placement")) {
      placements[c.hostId] ??= {};
      if (c.operation.startsWith("Remove")) delete placements[c.hostId][id];
      else placements[c.hostId][id] = { ...c.placement };
    } else if (c.operation.endsWith("Slot")) {
      const apps = objectValue(libraries[id]?.applications);
      if (c.operation.startsWith("Remove")) delete apps[c.entityId!];
      else
        apps[c.entityId!] = { ...objectValue(apps[c.entityId!]), ...c.entity };
      libraries[id] = { ...libraries[id], applications: apps };
    } else if (c.setting) {
      let target: ObjectValue;
      if (c.hostId) {
        placements[c.hostId] ??= {};
        const member = objectValue(placements[c.hostId][id]);
        target = objectValue(member.overrides);
        member.overrides = target;
        placements[c.hostId][id] = member;
      } else if (c.entityId) {
        libraries[id] ??= {};
        const apps = objectValue(libraries[id].applications);
        const slot = objectValue(apps[c.entityId!]);
        target = objectValue(slot.overrides);
        slot.overrides = target;
        apps[c.entityId!] = slot;
        libraries[id].applications = apps;
      } else {
        libraries[id] ??= {};
        target = objectValue(libraries[id].overrides);
        libraries[id].overrides = target;
      }
      const fields = c.property ? objectValue(target[c.property]) : target;
      if (c.operation.startsWith("Remove")) delete fields[c.setting];
      else
        Object.defineProperty(fields, c.setting, {
          value: c.value,
          enumerable: true,
          writable: true,
          configurable: true,
        });
      if (c.property) target[c.property] = fields;
    }
  }
  return { libraries, placements };
}
