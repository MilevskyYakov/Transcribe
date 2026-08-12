import { afterEach, describe, expect, it } from "vitest";
import {
  AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY,
  DEFAULT_MODEL_STORAGE_KEY,
  isTauriRuntime,
  loadWebAutosaveMarkdownDir,
  loadWebDefaultModel,
  resolveAppEnvironment,
  saveDefaultModel
} from "./appEnvironment";

describe("app environment", () => {
  const values = new Map<string, string>();

  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value)
    }
  });

  afterEach(() => {
    if (typeof window !== "undefined") {
      delete window.__TAURI_INTERNALS__;
    }
    localStorage.clear();
  });

  it("uses the web fallback outside Tauri", async () => {
    const environment = await resolveAppEnvironment("http://127.0.0.1:8765");

    expect(isTauriRuntime()).toBe(false);
    expect(environment).toEqual({
      apiBaseUrl: "http://127.0.0.1:8765",
      isTauri: false
    });
  });

  it("persists the default model in localStorage outside Tauri", async () => {
    await expect(saveDefaultModel(" tiny ", false)).resolves.toBe("tiny");

    expect(localStorage.getItem(DEFAULT_MODEL_STORAGE_KEY)).toBe("tiny");
    expect(loadWebDefaultModel()).toBe("tiny");
  });

  it("migrates the legacy default model storage key", () => {
    localStorage.setItem("transcribe-doc-default-model", "small");

    expect(loadWebDefaultModel()).toBe("small");
    expect(localStorage.getItem(DEFAULT_MODEL_STORAGE_KEY)).toBe("small");
  });

  it("migrates legacy browser settings without overriding Mnema values", () => {
    localStorage.setItem("transcribe-doc-default-model", "small");
    localStorage.setItem("transcribe-doc-autosave-markdown-dir", "/legacy/output");
    localStorage.setItem(DEFAULT_MODEL_STORAGE_KEY, "large-v3");

    expect(loadWebDefaultModel()).toBe("large-v3");
    expect(loadWebAutosaveMarkdownDir()).toBe("/legacy/output");
    expect(localStorage.getItem(AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY)).toBe("/legacy/output");
    expect(localStorage.getItem("transcribe-doc-autosave-markdown-dir")).toBe("/legacy/output");
  });
});
