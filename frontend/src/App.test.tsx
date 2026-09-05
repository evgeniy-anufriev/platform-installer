import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("UI-01B read-only shell", () => {
	it("opens and closes a Core snapshot without exposing edit actions", async () => {
		const api = { chooseProject: vi.fn().mockResolvedValue({ status: "OPEN", root: "C:/fixture", snapshot: { status: "PASS", project: { name: "Fixture" }, projectRevision: "sha256:abc", snapshotFingerprint: "sha256:def", hosts: { node1: {} }, serviceDeployments: {}, pki: {}, findings: [], documents: [] } }), chooseProjectParent: vi.fn(), createProject: vi.fn(), closeProject: vi.fn().mockResolvedValue({ status: "NO_PROJECT" }) };
    render(<App api={api} />);
    await userEvent.click(screen.getByRole("button", { name: "Открыть папку проекта" }));
    expect(await screen.findByRole("heading", { name: "Fixture" })).toBeTruthy();
    expect(screen.getByText("Только чтение")).toBeTruthy();
    expect(screen.queryByText("Сохранить")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Закрыть проект" }));
		expect(await screen.findByText("Выберите существующий проект или создайте новый")).toBeTruthy();
	});

	it("creates and renders an empty managed project without a Core snapshot", async () => {
		const api = {
			chooseProject: vi.fn(), chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"), closeProject: vi.fn(),
			createProject: vi.fn().mockResolvedValue({ status: "OPEN", root: "C:/Projects/new-project", classification: "EMPTY_MANAGED_PROJECT", project: { id: "project-0123456789abcdef", name: "New Project", source: { id: "default", bundleDigest: "sha256:bundle", catalogDigest: "sha256:catalog" } }, counts: { servers: 0, deployments: 0, runs: 0 } }),
		};
		render(<App api={api} />);
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" })[0]);
		await userEvent.type(screen.getByLabelText("Название проекта"), "New Project");
		await userEvent.click(screen.getByRole("button", { name: "Выбрать parent" }));
		await userEvent.clear(screen.getByLabelText("Название проекта"));
		await userEvent.type(screen.getByLabelText("Название проекта"), "Renamed Project");
		expect((screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value).toBe("C:/Projects\\Renamed Project");
		await userEvent.clear(screen.getByLabelText("Новая папка проекта"));
		await userEvent.type(screen.getByLabelText("Новая папка проекта"), "D:/Manual/custom-folder");
		await userEvent.clear(screen.getByLabelText("Название проекта"));
		await userEvent.type(screen.getByLabelText("Название проекта"), "Final Project");
		expect((screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value).toBe("D:/Manual/Final Project");
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!);
		expect(await screen.findByRole("heading", { name: "Проект ещё не настроен" })).toBeTruthy();
		expect(screen.getByText("Не создан")).toBeTruthy();
		expect(api.createProject).toHaveBeenCalledWith({ projectRoot: "D:/Manual/Final Project", displayName: "Final Project", compatibilitySourceId: "default" });
	});

	it("shows a create error immediately instead of keeping its modal open", async () => {
		const api = {
			chooseProject: vi.fn(), chooseProjectParent: vi.fn(), closeProject: vi.fn(),
			createProject: vi.fn().mockResolvedValue({ status: "ERROR", error: { code: "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE", message: "Нет проверенного local source." } }),
		};
		render(<App api={api} />);
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" })[0]);
		await userEvent.type(screen.getByLabelText("Название проекта"), "Project");
		await userEvent.type(screen.getByLabelText("Новая папка проекта"), "C:/Projects/project");
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!);
		expect(await screen.findByText("Нет проверенного local source.")).toBeTruthy();
		expect(screen.queryByRole("heading", { name: "Создать проект" })).toBeNull();
	});

	it("requires a project name and never calls the backend without one", async () => {
		const api = { chooseProject: vi.fn(), chooseProjectParent: vi.fn().mockResolvedValue("C:/Projects"), closeProject: vi.fn(), createProject: vi.fn() };
		render(<App api={api} />);
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" })[0]);
		await userEvent.click(screen.getByRole("button", { name: "Выбрать parent" }));
		expect((screen.getByLabelText("Новая папка проекта") as HTMLInputElement).value).toBe("C:/Projects\\");
		await userEvent.click(screen.getAllByRole("button", { name: "Создать проект" }).at(-1)!);
		expect((await screen.findByRole("alert")).textContent).toContain("Заполните «Название проекта»");
		expect(api.createProject).not.toHaveBeenCalled();
	});
});
