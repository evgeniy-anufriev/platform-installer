import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationsPage } from "./ApplicationsPage";
import { applicationDraft, type ApplicationIntent } from "./application-draft";
import type { OpenResult, RuntimeSecretDescriptorOperation } from "./backend";

const managed = {
  projectRevision: "revision",
  servers: {
    node1: {
      hostId: "node1",
    },
  },
  deployments: {
    docker: {
      serviceType: "docker",
    },
  },
  applicationLibraries: {
    sdku: {
      libraryRef: "sdku@1.0.0",
      runtimeRef: "docker",
      applications: {
        gateway: {
          overrides: {
            ports: {
              http: {
                published: 28480,
              },
            },
            parameters: {
              PASSWORD: "user-owned-parameter",
            },
          },
        },
      },
    },
  },
  applicationPlacements: {
    node1: {
      sdku: {
        overrides: {},
      },
    },
  },
  applicationPackages: {
    "library:sdku@1.0.0": {
      kind: "library",
      ref: "sdku@1.0.0",
      definition: {
        slots: {
          gateway: {
            applicationRef: "gateway@1.0.0",
          },
        },
      },
    },
    "application:gateway@1.0.0": {
      kind: "application",
      ref: "gateway@1.0.0",
      definition: {
        defaults: {
          image: "approved/gateway:1",
          ports: {
            http: {
              published: 10101,
              container: 8080,
            },
          },
          accounts: {
            postgres: {
              mode: "managed",
              credentials: {
                username: {
                  source: {
                    kind: "literal",
                    value: "qa",
                  },
                },
                password: {
                  source: {
                    kind: "runtime_secret_ref",
                    ref: "qa-password",
                  },
                },
              },
            },
          },
        },
        connections: {
          postgres: {
            library_binding: "db",
          },
          kafka: {
            library_binding: "messaging",
          },
        },
      },
    },
  },
} as unknown as NonNullable<OpenResult["managed"]>;
function Harness({
  calls,
  dirty = vi.fn(),
  accept = true,
}: {
  calls: ApplicationIntent[];
  dirty?: (value: boolean) => void;
  accept?: boolean;
}) {
  const [intents, setIntents] = useState<ApplicationIntent[]>([]);
  return (
    <ApplicationsPage
      managed={managed}
      snapshot={undefined}
      intents={intents}
      busy={false}
      onAppend={async (c) => {
        if (!accept) return false;
        calls.push(c);
        setIntents((v) => [...v, c]);
        return true;
      }}
      onAmend={async (previous, next) => {
        if (next) calls.push(next);
        setIntents((v) =>
          v.flatMap((i) => (i === previous ? (next ? [next] : []) : [i])),
        );
        return true;
      }}
      onReview={vi.fn()}
      onInstallation={vi.fn()}
      onDirtyChange={dirty}
      draftActive={false}
      onImport={vi.fn().mockResolvedValue(true)}
    />
  );
}
async function selectSlot() {
  await userEvent.click(screen.getByRole("button", { name: "↳ gateway" }));
}
describe("application editor", () => {
  it("reuses public descriptors across libraries and refreshes them for a new saved revision", async () => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
    };
    const view = structuredClone(managed);
    Object.assign(view.applicationLibraries, {
      cspa: structuredClone(view.applicationLibraries.sdku),
    });
    let revision = "revision";
    const load = vi.fn(async (): Promise<RuntimeSecretDescriptorOperation> => ({
      status: "READY",
      projectRevision: revision,
      descriptorSetFingerprint: "fingerprint",
      applicationInputs: ["sdku", "cspa"].map((lib) => ({
        requirementRef: lib,
        purpose: "APPLICATION_SECRET",
        sourceRef: lib,
        displayLabel: lib + " input",
        providerDeployment: null,
        applicationLibraries: [lib],
        hosts: ["node1"],
        operations: [
          "APPLICATION_LIBRARIES_APPLY",
          "APPLICATION_LIBRARIES_VERIFY",
        ],
      })),
    }));
    const save = vi.fn().mockResolvedValue(undefined);
    const props = {
      snapshot: undefined,
      intents: [],
      busy: false,
      draftActive: false,
      onAppend: vi.fn(),
      onAmend: vi.fn(),
      onReview: vi.fn(),
      onInstallation: vi.fn(),
      onDirtyChange: vi.fn(),
      onImport: vi.fn(),
      loadSecrets: load,
      saveSecrets: save,
    };
    const rendered = render(<ApplicationsPage {...props} managed={view} />);
    for (const lib of ["sdku", "cspa"]) {
      const group = screen
        .getByText(lib, { exact: true })
        .closest("button")!.parentElement!;
      await userEvent.click(
        within(group).getByRole("button", { name: "↳ gateway" }),
      );
      await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
      await userEvent.click(
        screen.getByRole("button", { name: "Секреты: " + lib + " / gateway" }),
      );
      await userEvent.type(
        await screen.findByLabelText(lib + " input"),
        "synthetic-only",
      );
      await userEvent.click(
        screen.getByRole("button", { name: "Сохранить в сессии" }),
      );
    }
    expect(load).toHaveBeenCalledTimes(1);
    expect(save.mock.calls.map(([input]) => input.applicationLibrary)).toEqual([
      "sdku",
      "cspa",
    ]);
    revision = "new-revision";
    rendered.rerender(
      <ApplicationsPage
        {...props}
        managed={Object.assign(structuredClone(view), {
          projectRevision: revision,
        })}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Секреты: cspa / gateway" }),
    );
    await screen.findByLabelText("cspa input");
    expect(load).toHaveBeenCalledTimes(2);
  });
  it.each([true, false])(
    "clears only accepted create form dirty state (accepted=%s)",
    async (accept) => {
      const calls: ApplicationIntent[] = [],
        dirty = vi.fn();
      render(<Harness calls={calls} dirty={dirty} accept={accept} />);
      await userEvent.click(
        screen.getByRole("button", { name: "Добавить библиотеку" }),
      );
      await userEvent.type(screen.getByLabelText("ID библиотеки"), "newlib");
      await userEvent.selectOptions(
        screen.getByLabelText("Пакет"),
        "sdku@1.0.0",
      );
      await userEvent.selectOptions(
        screen.getByLabelText("Docker runtime"),
        "docker",
      );
      await userEvent.click(screen.getByRole("button", { name: "В черновик" }));
      const review = screen.getByRole("button", {
        name: "Показать изменения проекта",
      }) as HTMLButtonElement;
      expect(review.disabled).toBe(!accept);
      expect(dirty).toHaveBeenLastCalledWith(!accept);
      if (!accept)
        expect(
          (screen.getByLabelText("ID библиотеки") as HTMLInputElement).value,
        ).toBe("newlib");
      else
        expect(calls[0].operation).toBe("CreateApplicationLibraryDeployment");
    },
  );
  it("opens package defaults without commands, saves image override and removes it on reset", async () => {
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} />);
    await selectSlot();
    expect(calls).toHaveLength(0);
    const image = screen.getByLabelText("Образ · image");
    expect((image as HTMLInputElement).value).toBe("approved/gateway:1");
    await userEvent.clear(image);
    await userEvent.type(image, "approved/gateway:2");
    await userEvent.click(
      within(image.closest(".application-field")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect(calls[0]).toMatchObject({
      operation: "SetApplicationLibraryOverride",
      entityId: "gateway",
      setting: "image",
      value: "approved/gateway:2",
    });
    await userEvent.click(
      within(image.closest(".application-field")!).getByRole("button", {
        name: "Сбросить к default",
      }),
    );
    expect(calls[1].operation).toBe("RemoveApplicationLibraryOverride");
    expect(
      (screen.getByLabelText("Образ · image") as HTMLInputElement).value,
    ).toBe("approved/gateway:1");
  });
  it("changes only host port and reset does not copy container default into authored mapping", async () => {
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} />);
    await selectSlot();
    const host = screen.getByLabelText("Порт хоста");
    expect((host as HTMLInputElement).value).toBe("28480");
    expect(
      (screen.getByLabelText("Порт контейнера") as HTMLInputElement).value,
    ).toBe("8080");
    await userEvent.clear(host);
    await userEvent.type(host, "28481");
    await userEvent.click(
      within(host.closest(".application-field")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect(calls[0]).toMatchObject({
      property: "ports",
      setting: "http",
      value: { published: 28481 },
    });
    await userEvent.click(
      within(host.closest(".application-field")!).getByRole("button", {
        name: "Сбросить к default",
      }),
    );
    expect(calls[1]).toMatchObject({
      operation: "RemoveApplicationLibraryOverride",
      property: "ports",
      setting: "http",
    });
    expect(calls[1]).not.toHaveProperty("value");
  });
  it("preserves another local input when saving one field", async () => {
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} />);
    await selectSlot();
    const image = screen.getByLabelText("Образ · image"),
      host = screen.getByLabelText("Порт хоста");
    await userEvent.clear(image);
    await userEvent.type(image, "approved/gateway:local");
    await userEvent.clear(host);
    await userEvent.type(host, "30000");
    await userEvent.click(
      within(host.closest(".application-field")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect((image as HTMLInputElement).value).toBe("approved/gateway:local");
    expect(screen.getByRole("status").textContent).toContain("Есть ввод");
  });
  it("shows every declared connection and rejects literal password entry in typed source controls", async () => {
    render(<Harness calls={[]} />);
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    expect(screen.getByRole("heading", { name: "postgres" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "kafka" })).toBeTruthy();
    const password = screen.getByRole("group", { name: "Пароль" });
    expect(
      within(password).queryByRole("option", { name: "Имя пользователя" }),
    ).toBeNull();
    expect(
      within(password).getByRole("option", {
        name: "Существующий Vault secret",
      }),
    ).toBeTruthy();
  });
  it("keeps authored opaque fields and isolates deployments in local draft projection", () => {
    const original = structuredClone(managed);
    const result = applicationDraft(managed, [
      {
        operation: "SetApplicationLibraryOverride",
        deploymentId: "sdku",
        entityId: "gateway",
        setting: "image",
        value: "next",
      },
    ]);
    expect(result.libraries.sdku.applications).toMatchObject({
      gateway: {
        overrides: {
          parameters: { PASSWORD: "user-owned-parameter" },
          ports: { http: { published: 28480 } },
          image: "next",
        },
      },
    });
    expect(managed).toEqual(original);
  });
});
