import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { ServerInformationDialog, ServerInformationText } from "./ServerInformationDialog";

it("requests one confirmation token under StrictMode effect replay", async () => {
  const onProbe=vi.fn().mockResolvedValue({status:"APPROVAL_REQUIRED",probeId:"current",fingerprint:"SHA256:known"});
  const onCheck=vi.fn().mockResolvedValue({status:"CHECKED"});
  render(<StrictMode><ServerInformationDialog hostId="node2" onProbe={onProbe} onCheck={onCheck} onResult={vi.fn()} onClose={vi.fn()}/></StrictMode>);
  await screen.findByText("SHA256:known");
  expect(onProbe).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button",{name:"Подтверждаю совпадение"}));
  await waitFor(()=>expect(onCheck).toHaveBeenCalledWith("current"));
});

it("requires explicit fingerprint confirmation before connecting", async () => {
  const onProbe = vi.fn().mockResolvedValue({status:"APPROVAL_REQUIRED",probeId:"opaque",fingerprint:"SHA256:known",keyType:"ssh-ed25519"});
  const onCheck = vi.fn().mockResolvedValue({status:"CHECKED",hostId:"node1"});
  const onClose=vi.fn();
  render(<ServerInformationDialog hostId="node1" onProbe={onProbe} onCheck={onCheck} onResult={vi.fn()} onClose={onClose}/>);
  expect(await screen.findByText("SHA256:known")).toBeTruthy();
  expect(onCheck).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Подтверждаю совпадение"}));
  await waitFor(()=>expect(onCheck).toHaveBeenCalledWith("opaque"));
  await waitFor(()=>expect(onClose).toHaveBeenCalled());
});

it("cancellation never dispatches a connection", async () => {
  const onCheck=vi.fn();const onClose=vi.fn();
  render(<ServerInformationDialog hostId="node1" onProbe={vi.fn().mockResolvedValue({status:"APPROVAL_REQUIRED",probeId:"opaque",fingerprint:"SHA256:known"})} onCheck={onCheck} onResult={vi.fn()} onClose={onClose}/>);
  await screen.findByText("SHA256:known");
  fireEvent.click(screen.getByRole("button",{name:"Отмена"}));
  expect(onClose).toHaveBeenCalled();expect(onCheck).not.toHaveBeenCalled();
});

it("shows only agreed observations and Moscow timestamps", () => {
  render(<ServerInformationText value={{status:"CHECKED",information:{hostname:"node1",os:"RED OS",osVersion:"8",architecture:"x86_64",cpuCount:8,memoryBytes:16*1024**3,serverTime:"2026-10-08T16:00:00Z",checkedAt:"2026-10-08T16:01:00Z"}}}/>);
  expect(screen.getByText("CPU: 8 · RAM: 16 ГБ")).toBeTruthy();
  expect(screen.getByText(/Проверен: 08.10.2026, 19:01 МСК/)).toBeTruthy();
});
