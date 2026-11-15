import { beforeEach, describe, expect, it } from "vitest";
import { useApp } from "../src/store";

beforeEach(() => useApp.setState(useApp.getInitialState(), true));

describe("store partagé", () => {
  it("la démonstration est désactivée par défaut et réinitialise les dates", () => {
    expect(useApp.getState().demo).toBe(false);
    useApp.getState().setDate("2026-03-04");
    useApp.getState().setDemo(true);
    expect(useApp.getState().demo).toBe(true);
    expect(useApp.getState().date).toBeNull();
  });
  it("ajout, retrait et réordonnancement des couches", () => {
    const s = useApp.getState();
    s.toggleLayer("nisar-gcov-hv", true);
    expect(useApp.getState().activeLayers).toEqual(["nisar-gcov-hh", "nisar-gcov-hv"]);
    useApp.getState().moveLayer("nisar-gcov-hv", -1);
    expect(useApp.getState().activeLayers).toEqual(["nisar-gcov-hv", "nisar-gcov-hh"]);
    useApp.getState().moveLayer("nisar-gcov-hv", -1); // déjà en bas : sans effet
    expect(useApp.getState().activeLayers[0]).toBe("nisar-gcov-hv");
    useApp.getState().toggleLayer("nisar-gcov-hh", false);
    expect(useApp.getState().activeLayers).toEqual(["nisar-gcov-hv"]);
  });
});
