import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EvidenceStrip from "./EvidenceStrip";
import type { Study } from "../api/client";

const crop = (type: NonNullable<Study["evidence"]>[number]["type"], x: number): NonNullable<Study["evidence"]>[number] => ({
  type,
  x,
  y: 10,
  quadrant: "ST",
  distanceToFoveaDD: 1.4,
  cropUrl: `/ev/${type}.png`,
  criterionKey: "icdr.l2.haemorrhages_multi_quadrant",
});

describe("EvidenceStrip", () => {
  it("renders a native crop tile for each finding", () => {
    render(<EvidenceStrip evidence={[crop("MA", 1), crop("HE", 2)]} />);
    const tiles = screen.getAllByTestId("evidence-tile");
    expect(tiles).toHaveLength(2);
    expect(tiles[0]).toHaveAttribute("data-type", "MA");
    expect(tiles[1]).toHaveAttribute("data-type", "HE");
    expect(screen.getByText("2 findings")).toBeInTheDocument();
  });

  it("shows an empty state when there are no crops", () => {
    render(<EvidenceStrip evidence={[]} />);
    expect(screen.getByText("No lesion crops for this image.")).toBeInTheDocument();
  });
});
