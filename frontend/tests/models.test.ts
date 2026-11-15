import { describe, expect, it } from "vitest";
import {
  L_BAND_WAVELENGTH_M, classifyFlood, floodBackscatterDb, fringeCount, fromDb, insarPhase, mmPerFringe, opticalVisibility,
  radarVisibility, rgbComposite, roughnessBackscatterDb, toDb, wrapPhase,
} from "../src/sim/models";
import { fmtDb, nearest } from "../src/lib/format";

describe("conversions dB", () => {
  it("0,1 linéaire vaut -10 dB et inversement", () => {
    expect(toDb(0.1)).toBeCloseTo(-10, 6);
    expect(fromDb(-10)).toBeCloseTo(0.1, 6);
  });
});

describe("jour, nuit, nuages", () => {
  it("l'optique est aveugle la nuit, le radar non", () => {
    expect(opticalVisibility(0, 0)).toBe(0);
    expect(radarVisibility(1)).toBeGreaterThan(0.9);
  });
  it("les nuages réduisent l'optique", () => {
    expect(opticalVisibility(1, 0.8)).toBeCloseTo(0.2, 6);
  });
});

describe("rugosité", () => {
  it("le retour augmente avec la rugosité", () => {
    expect(roughnessBackscatterDb(0.9, 35)).toBeGreaterThan(roughnessBackscatterDb(0.1, 35));
  });
});

describe("eau et inondation", () => {
  it("eau calme détectée, eau agitée ou avec végétation émergée ratée", () => {
    expect(classifyFlood(floodBackscatterDb(0, false, true))).toBe("eau probable");
    expect(classifyFlood(floodBackscatterDb(15, false, true))).toBe("terre probable");
    expect(classifyFlood(floodBackscatterDb(0, true, true))).toBe("terre probable");
  });
});

describe("InSAR", () => {
  it("une demi-longueur d'onde de déplacement donne une frange complète (2π)", () => {
    expect(insarPhase(mmPerFringe())).toBeCloseTo(2 * Math.PI, 6);
    expect(fringeCount(mmPerFringe())).toBeCloseTo(1, 6);
  });
  it("une frange vaut environ 119 mm en bande L", () => {
    expect(mmPerFringe()).toBeCloseTo((L_BAND_WAVELENGTH_M / 2) * 1000, 6);
    expect(mmPerFringe()).toBeGreaterThan(110);
    expect(mmPerFringe()).toBeLessThan(125);
  });
  it("la phase enroulée reste dans [-π, π]", () => {
    for (const p of [-20, -3.5, 0, 3.5, 7, 100]) {
      const w = wrapPhase(p);
      expect(w).toBeGreaterThanOrEqual(-Math.PI - 1e-9);
      expect(w).toBeLessThanOrEqual(Math.PI + 1e-9);
    }
  });
});

describe("composite RVB", () => {
  it("reste entre 0 et 1", () => {
    for (const v of rgbComposite(10, -50).concat(rgbComposite(-60, 10))) { expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(1); }
  });
});

describe("format", () => {
  it("une valeur absente n'est jamais affichée comme 0", () => {
    expect(fmtDb(null)).toBe("non disponible");
    expect(fmtDb(undefined)).toBe("non disponible");
    expect(fmtDb(-7.234)).toBe("-7.2 dB");
  });
  it("nearest choisit la date réelle la plus proche", () => {
    expect(nearest(["2026-03-04", "2026-04-05"], "2026-04-01")).toBe("2026-04-05");
    expect(nearest([], "2026-04-01")).toBeNull();
  });
});
