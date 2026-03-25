import { describe, it, expect } from "vitest";
import Button from "../Button";

// @testing-library/react n'est pas installe,
// on teste uniquement que le composant s'importe correctement.

describe("Button", () => {
  it("existe et est exporte", () => {
    expect(Button).toBeDefined();
    expect(typeof Button).toBe("function");
  });
});
