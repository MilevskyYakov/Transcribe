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
