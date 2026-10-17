import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApplicationsPage } from "./ApplicationsPage";
import {
  applicationDraft,
  objectValue,
  type ApplicationIntent,
} from "./application-draft";
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
  snapshot,
  view = managed,
}: {
  calls: ApplicationIntent[];
  dirty?: (value: boolean) => void;
  accept?: boolean;
  snapshot?: OpenResult["snapshot"];
  view?: NonNullable<OpenResult["managed"]>;
}) {
  const [intents, setIntents] = useState<ApplicationIntent[]>([]);
  return (
    <ApplicationsPage
      managed={view}
      snapshot={snapshot}
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
  it("resets common overrides at library scope without creating a slot", async () => {
    const view = structuredClone(managed);
    objectValue(
      view.applicationPackages["library:sdku@1.0.0"].definition,
    ).defaults = { environment: { COMMON: "package" } };
    view.applicationLibraries.sdku.overrides = {
      environment: { COMMON: "site" },
    };
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} view={view} />);
    await userEvent.click(screen.getByRole("button", { name: /^sdku/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Общие параметры" }),
    );
    expect((screen.getByLabelText("COMMON") as HTMLInputElement).value).toBe(
      "site",
    );
    await userEvent.click(
      within(
        screen
          .getByLabelText("COMMON")
          .closest(".application-field") as HTMLElement,
      ).getByRole("button", { name: "Сбросить к default" }),
    );
    expect((screen.getByLabelText("COMMON") as HTMLInputElement).value).toBe(
      "package",
    );
    expect(calls.at(-1)).toMatchObject({
      operation: "RemoveApplicationLibraryOverride",
      entityId: "",
      setting: "environment",
    });
    const draft = applicationDraft(view, calls);
    expect(objectValue(draft.libraries.sdku.applications)[""]).toBeUndefined();
  });

  it("uses the Core inherited baseline and marks it stale after instance reset", async () => {
    const view = structuredClone(managed);
    objectValue(
      view.applicationPackages["library:sdku@1.0.0"].definition,
    ).defaults = { environment: { COMMON: "package" } };
    objectValue(
      objectValue(
        objectValue(view.applicationLibraries.sdku.applications).gateway,
      ).overrides,
    ).environment = { COMMON: "instance" };
    const snapshotData = {
      projectRevision: "revision",
      applicationLibraries: {
        libraries: {
          sdku: {
            instances: {
              gateway: {
                slotId: "gateway",
                placements: {
                  node1: {
                    inherited: {
                      environment: {
                        COMMON: "site",
                        ONLY_INHERITED: "from-core",
                      },
                    },
                  },
                  node2: {
                    inherited: {
                      environment: { ONLY_INHERITED: "second-host" },
                    },
                  },
                },
              },
            },
          },
        },
      },
    };
    const snapshot = snapshotData as unknown as OpenResult["snapshot"];
    const calls: ApplicationIntent[] = [];
    const rendered = render(
      <Harness calls={calls} view={view} snapshot={snapshot} />,
    );
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Запуск" }));
    expect((screen.getByLabelText("COMMON") as HTMLInputElement).value).toBe(
      "instance",
    );
    expect(
      (screen.getByLabelText("ONLY_INHERITED") as HTMLInputElement).value,
    ).toBe("from-core");
    await userEvent.selectOptions(
      screen.getByLabelText("Наследуемые значения для сервера"),
      "node2",
    );
    expect(
      (screen.getByLabelText("ONLY_INHERITED") as HTMLInputElement).value,
    ).toBe("second-host");
    Object.assign(
      snapshotData.applicationLibraries.libraries.sdku.instances.gateway,
      {
        placements: {
          node3: { inherited: { environment: { ONLY_INHERITED: "new-host" } } },
          node4: {
            inherited: { environment: { ONLY_INHERITED: "another-host" } },
          },
        },
      },
    );
    rendered.rerender(
      <Harness
        calls={calls}
        view={view}
        snapshot={snapshotData as unknown as OpenResult["snapshot"]}
      />,
    );
    expect(
      (
        screen.getByLabelText(
          "Наследуемые значения для сервера",
        ) as HTMLSelectElement
      ).value,
    ).toBe("node3");
    expect(
      (screen.getByLabelText("ONLY_INHERITED") as HTMLInputElement).value,
    ).toBe("new-host");
    await userEvent.click(
      within(
        screen
          .getByLabelText("COMMON")
          .closest(".application-field") as HTMLElement,
      ).getByRole("button", { name: "Сбросить к default" }),
    );
    expect(calls.at(-1)).toMatchObject({
      operation: "RemoveApplicationLibraryOverride",
      entityId: "gateway",
      setting: "environment",
    });
    expect(
      screen.getByText(/Унаследованные значения требуют проверки/),
    ).toBeTruthy();
    expect(screen.queryByLabelText("ONLY_INHERITED")).toBeNull();
  });
  it("shows library and host port sources even without application defaults or instance overrides", async () => {
    const view = structuredClone(managed);
    delete objectValue(
      objectValue(
        view.applicationPackages["application:gateway@1.0.0"].definition,
      ).defaults,
    ).ports;
    delete objectValue(
      objectValue(
        objectValue(view.applicationLibraries.sdku.applications).gateway,
      ).overrides,
    ).ports;
    objectValue(
      objectValue(view.applicationPackages["library:sdku@1.0.0"].definition)
        .slots,
    ).gateway = {
      applicationRef: "gateway@1.0.0",
      overrides: { ports: { http: { published: 10102, container: 8080 } } },
    };
    objectValue(view.applicationPlacements.node1.sdku).overrides = {
      ports: { http: { published: 3333 } },
    };
    const snapshot = {
      projectRevision: "verified-revision",
      applicationLibraries: {
        libraries: {
          sdku: {
            instances: {
              "gateway-sdku": {
                slotId: "gateway",
                placements: {
                  node1: {
                    ports: { http: { published: 3333, container: 8080 } },
                  },
                },
              },
            },
          },
        },
      },
    } as unknown as OpenResult["snapshot"];
    render(<Harness calls={[]} view={view} snapshot={snapshot} />);
    await selectSlot();
    await userEvent.click(screen.getByText("Источники настроек портов"));
    expect(screen.getByText("10102 → 8080")).toBeTruthy();

    expect(screen.getByText("Пакет библиотеки · gateway")).toBeTruthy();
    expect(screen.getByText("Размещение · node1")).toBeTruthy();
    expect(screen.getByText(/Core · node1 · verified-revision/)).toBeTruthy();
    expect(screen.getByText("3333 → —")).toBeTruthy();
    expect(screen.getByText("3333 → 8080")).toBeTruthy();
  });
  it("displays the Core instance identity without inventing a name or enabling rename", async () => {
    const snapshot = {
      applicationLibraries: {
        libraries: {
          sdku: { instances: { "core-gateway-name": { slotId: "gateway" } } },
        },
      },
    } as unknown as OpenResult["snapshot"];
    render(<Harness calls={[]} snapshot={snapshot} />);
    await selectSlot();
    expect(screen.getByText("core-gateway-name")).toBeTruthy();
    expect(
      screen.queryByRole("textbox", { name: /Имя экземпляра/ }),
    ).toBeNull();
  });
  it("keeps General focused and moves configuration parameters to Startup", async () => {
    render(<Harness calls={[]} />);
    await selectSlot();
    expect(
      screen.getByRole("heading", { name: "Проверка готовности" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: "Параметры приложения" }),
    ).toBeNull();
    expect(screen.queryByLabelText("PASSWORD", { exact: true })).toBeNull();
    expect(screen.getByLabelText("Порт хоста")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Порты" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Подключения" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Параметры" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Запуск" }));
    expect(
      screen.getByRole("heading", { name: "Настройки конфигурации" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("PASSWORD", { exact: true })).toBeTruthy();
  });
  it("hides empty configuration settings while keeping ENV on Startup", async () => {
    const view = structuredClone(managed);
    delete objectValue(
      objectValue(
        objectValue(view.applicationLibraries.sdku.applications).gateway,
      ).overrides,
    ).parameters;
    render(<Harness calls={[]} view={view} />);
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Запуск" }));
    expect(
      screen.queryByRole("heading", { name: "Настройки конфигурации" }),
    ).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Переменные окружения (ENV)" }),
    ).toBeTruthy();
  });
  it("shows configuration settings declared only by the package", async () => {
    const view = structuredClone(managed);
    delete objectValue(
      objectValue(
        objectValue(view.applicationLibraries.sdku.applications).gateway,
      ).overrides,
    ).parameters;
    objectValue(
      objectValue(
        view.applicationPackages["application:gateway@1.0.0"].definition,
      ).defaults,
    ).parameters = { request_timeout: 30 };
    render(<Harness calls={[]} view={view} />);
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Запуск" }));
    expect(
      (
        screen.getByLabelText("request_timeout", {
          exact: true,
        }) as HTMLInputElement
      ).value,
    ).toBe("30");
  });
  it("saves configuration parameters through their existing setting, without changing ENV", async () => {
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} />);
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Запуск" }));
    const input = screen.getByLabelText("PASSWORD", { exact: true });
    await userEvent.clear(input);
    await userEvent.type(input, "user-owned-updated");
    await userEvent.click(
      within(input.closest(".application-field")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect(calls).toEqual([
      expect.objectContaining({
        operation: "SetApplicationLibraryOverride",
        setting: "parameters",
        value: { PASSWORD: "user-owned-updated" },
      }),
    ]);
  });
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
  it("defaults a new library ID from its package without replacing a custom ID", async () => {
    render(<Harness calls={[]} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Добавить библиотеку" }),
    );
    await userEvent.selectOptions(screen.getByLabelText("Пакет"), "sdku@1.0.0");
    expect(
      (screen.getByLabelText("ID библиотеки") as HTMLInputElement).value,
    ).toBe("sdku");
    await userEvent.clear(screen.getByLabelText("ID библиотеки"));
    await userEvent.type(screen.getByLabelText("ID библиотеки"), "custom");
    await userEvent.selectOptions(screen.getByLabelText("Пакет"), "sdku@1.0.0");
    expect(
      (screen.getByLabelText("ID библиотеки") as HTMLInputElement).value,
    ).toBe("custom");
    await userEvent.click(
      screen.getByRole("button", { name: "Сбросить ID к имени библиотеки" }),
    );
    expect(
      (screen.getByLabelText("ID библиотеки") as HTMLInputElement).value,
    ).toBe("sdku");
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
    const image = screen.getByLabelText("Образ контейнера");
    expect((image as HTMLInputElement).value).toBe("approved/gateway:1");
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить: Образ контейнера" }),
    );
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
      (screen.getByLabelText("Образ контейнера") as HTMLInputElement).value,
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
  it("preserves another local port input when saving one field", async () => {
    const calls: ApplicationIntent[] = [];
    render(<Harness calls={calls} />);
    await selectSlot();

    const container = screen.getByLabelText("Порт контейнера"),
      host = screen.getByLabelText("Порт хоста");
    await userEvent.click(
      screen.getByRole("button", { name: "Переопределить: Порт контейнера" }),
    );
    await userEvent.clear(container);
    await userEvent.type(container, "8081");
    await userEvent.clear(host);
    await userEvent.type(host, "30000");
    await userEvent.click(
      within(host.closest(".application-field")!).getByRole("button", {
        name: "В черновик",
      }),
    );
    expect((container as HTMLInputElement).value).toBe("8081");
    expect(screen.getByRole("status").textContent).toContain("Есть ввод");
  });
  it("shows every declared connection and rejects literal password entry in typed source controls", async () => {
    render(<Harness calls={[]} />);
    await selectSlot();
    await userEvent.click(screen.getByRole("button", { name: "Секреты" }));
    expect(screen.getByRole("heading", { name: "postgres" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "kafka" })).toBeNull();
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
