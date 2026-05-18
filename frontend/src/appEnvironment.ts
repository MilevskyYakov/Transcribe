import type { AppEnvironment } from "./types";

interface TauriBootstrapPayload {
  api_base_url: string;
  default_model_name?: string | null;
  app_data_dir: string;
  cache_dir: string;
  output_dir: string;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  ffmpeg_path?: string | null;
  ffprobe_path?: string | null;
}

export const DEFAULT_MODEL_STORAGE_KEY = "transcribe-doc-default-model";

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;
}

export async function resolveAppEnvironment(defaultApiBase: string): Promise<AppEnvironment> {
  if (!isTauriRuntime()) {
    return {
      apiBaseUrl: defaultApiBase,
      isTauri: false
    };
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const payload = await invoke<TauriBootstrapPayload>("app_bootstrap");
    return {
      apiBaseUrl: normalizeBridgeValue(payload.api_base_url, defaultApiBase),
      defaultModelName: payload.default_model_name ?? null,
      appDataDir: payload.app_data_dir,
      cacheDir: payload.cache_dir,
      outputDir: payload.output_dir,
      ffmpegAvailable: payload.ffmpeg_available,
      ffprobeAvailable: payload.ffprobe_available,
      ffmpegPath: payload.ffmpeg_path,
      ffprobePath: payload.ffprobe_path,
      isTauri: true
    };
  } catch (error) {
    console.error("Tauri bootstrap failed", error);
    return {
      apiBaseUrl: defaultApiBase,
      isTauri: true
    };
  }
}

export function loadWebDefaultModel(): string | null {
  return normalizeOptionalValue(storage()?.getItem(DEFAULT_MODEL_STORAGE_KEY));
}

export async function saveDefaultModel(modelName: string, isTauri: boolean): Promise<string> {
  const normalized = normalizeOptionalValue(modelName);
  if (!normalized) {
    throw new Error("Model name cannot be empty");
  }
  if (isTauri) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<string>("set_default_model", { modelName: normalized });
  }
  storage()?.setItem(DEFAULT_MODEL_STORAGE_KEY, normalized);
  return normalized;
}

function normalizeBridgeValue(value: string | null | undefined, fallback: string): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed.replace(/\/+$/, "") : fallback;
}

function normalizeOptionalValue(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

function storage(): Storage | null {
  return typeof localStorage === "undefined" ? null : localStorage;
}
