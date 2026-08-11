import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "./api";

describe("native job creation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends an absolute native media path and per-job destination to POST /jobs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ job: null }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    await new ApiClient("http://127.0.0.1:8765").createJob(
      "/Users/demo/meeting.m4a",
      "Meeting",
      "",
      "onnx",
      "large-v3",
      "/Users/demo/Documents"
    );

    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8765/jobs");
    expect(request.method).toBe("POST");
    expect(JSON.parse(String(request.body))).toMatchObject({
      input_path: "/Users/demo/meeting.m4a",
      display_title: "Meeting",
      final_markdown_dir: "/Users/demo/Documents"
    });
  });
});

describe("batch sessions", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates an ordered durable session and submits one canonical item", async () => {
    const batchSession = {
      session_id: "batch-1",
      created_at: "2026-08-11T00:00:00Z",
      common_output_dir: "/Users/demo/Documents",
      status: "active",
      totals: { total: 2, configure: 2, processing: 0, ready: 0, failed: 0 },
      items: []
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ batch_session: batchSession }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ batch_session: batchSession, job: { job_id: "job-1" } }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://127.0.0.1:8765");

    await client.createBatchSession([
      { inputPath: "/tmp/one.wav", sourceName: "one.wav" },
      { inputPath: "/tmp/two.wav", sourceName: "two.wav" }
    ], "/Users/demo/Documents");
    await client.submitBatchSessionItem(
      "batch-1",
      "item-1",
      "/tmp/one.wav",
      "Первый",
      "/Users/demo/Documents"
    );

    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)).items).toEqual([
      { input_path: "/tmp/one.wav", source_name: "one.wav" },
      { input_path: "/tmp/two.wav", source_name: "two.wav" }
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toMatchObject({
      input_path: "/tmp/one.wav",
      display_title: "Первый",
      final_markdown_dir: "/Users/demo/Documents"
    });
  });
});
