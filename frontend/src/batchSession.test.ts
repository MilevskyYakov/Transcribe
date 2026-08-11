import { describe, expect, it } from "vitest";
import { batchFilesMatch } from "./App";
import { batchItemStatusLabel } from "./components/BatchSessionPanel";
import type { BatchSessionItem } from "./types";

describe("batch session presentation", () => {
  it("uses accepted queue labels", () => {
    expect(batchItemStatusLabel("configure")).toBe("Настроить");
    expect(batchItemStatusLabel("processing")).toBe("Обрабатывается");
    expect(batchItemStatusLabel("ready")).toBe("Готово");
    expect(batchItemStatusLabel("failed")).toBe("Ошибка");
  });

  it("reattaches browser files only to the persisted ordered queue", () => {
    const items = ["one.wav", "two.wav"].map((source_name, index): BatchSessionItem => ({
      item_id: `item-${index + 1}`,
      position: index + 1,
      input_path: null,
      source_name,
      display_title: source_name,
      attempt_job_ids: [],
      status: "configure"
    }));

    expect(batchFilesMatch(items, [new File([], "one.wav"), new File([], "two.wav")])).toBe(true);
    expect(batchFilesMatch(items, [new File([], "two.wav"), new File([], "one.wav")])).toBe(false);
  });
});