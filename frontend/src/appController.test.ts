import { describe, expect, it } from "vitest";
import { createLatestRequest } from "./appController";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

describe("snapshot ownership", () => {
  it("ignores an older response that finishes after a newer refresh", async () => {
    const older = deferred<string[]>();
    const newer = deferred<string[]>();
    const applied: string[][] = [];
    const request = createLatestRequest();

    const olderRefresh = request(() => older.promise, (value) => applied.push(value));
    const newerRefresh = request(() => newer.promise, (value) => applied.push(value));
    newer.resolve(["new-job"]);
    await newerRefresh;
    older.resolve([]);
    await olderRefresh;

    expect(applied).toEqual([["new-job"]]);
  });
});