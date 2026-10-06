import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PosteriorBand from "./PosteriorBand";

describe("PosteriorBand", () => {
  it("renders five grade segments and the referable mass", () => {
    const posterior = [0.05, 0.1, 0.5, 0.25, 0.1];
    render(<PosteriorBand posterior={posterior} />);
    const segments = screen.getAllByTestId("posterior-segment");
    expect(segments).toHaveLength(5);
    expect(screen.getByTestId("posterior-referable")).toHaveTextContent("0.85");
    expect(screen.queryByTestId("posterior-threshold")).toBeNull();
  });

  it("draws a threshold rule only when a frozen operating point is supplied", () => {
    render(<PosteriorBand posterior={[0.2, 0.2, 0.2, 0.2, 0.2]} threshold={0.4} />);
    const line = screen.getByTestId("posterior-threshold");
    expect(line.style.left).toBe("40%");
  });
});
