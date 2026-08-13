import type { AppEnvironment, BackendLifecycle } from "./types";

interface TauriBootstrapPayload {
  api_base_url: string;
  default_model_name?: string | null;
  autosave_markdown_dir?: string | null;
  app_data_dir: string;
  cache_dir: string;
  model_dir?: string | null;
  output_dir: string;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  ffmpeg_path?: string | null;
  ffprobe_path?: string | null;
  backend_lifecycle?: BackendLifecycle | null;
  desktop_platform?: "macos" | "windows" | "unsupported";
  native_file_actions?: boolean;
}

export const DEFAULT_MODEL_STORAGE_KEY = "mnema-default-model";
export const AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY = "mnema-autosave-markdown-dir";
const LEGACY_DEFAULT_MODEL_STORAGE_KEY = "transcribe-doc-default-model";
const LEGACY_AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY = "transcribe-doc-autosave-markdown-dir";

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;
}

export function revealFileLabel(platform: AppEnvironment["desktopPlatform"]): string {
  return platform === "windows" ? "Показать в Explorer" : "Показать в Finder";
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
      autosaveMarkdownDir: payload.autosave_markdown_dir ?? null,
      appDataDir: payload.app_data_dir,
      cacheDir: payload.cache_dir,
      modelDir: payload.model_dir ?? null,
      outputDir: payload.output_dir,
      ffmpegAvailable: payload.ffmpeg_available,
      ffprobeAvailable: payload.ffprobe_available,
      ffmpegPath: payload.ffmpeg_path,
      ffprobePath: payload.ffprobe_path,
      backendLifecycle: payload.backend_lifecycle ?? null,
      desktopPlatform: payload.desktop_platform ?? "unsupported",
      nativeFileActions: payload.native_file_actions ?? false,
      isTauri: true
    };
  } catch (error) {
    console.error("Tauri bootstrap failed", error);
    return {
      apiBaseUrl: defaultApiBase,
      backendLifecycle: {
        state: "error",
        human_message: "Не удалось запустить",
        technical_detail: error instanceof Error ? error.message : String(error),
        last_check_at: null,
        recent_output: []
      },
      isTauri: true
    };
  }
}

export async function loadBackendStatus(isTauri: boolean): Promise<BackendLifecycle | null> {
  if (!isTauri) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<BackendLifecycle>("backend_status");
}

export async function markBackendOnline(isTauri: boolean): Promise<BackendLifecycle | null> {
  if (!isTauri) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<BackendLifecycle>("mark_backend_online");
}

export async function markBackendOffline(
  isTauri: boolean,
  detail: string
): Promise<BackendLifecycle | null> {
  if (!isTauri) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<BackendLifecycle>("mark_backend_offline", { detail });
}

export async function restartBackend(isTauri: boolean): Promise<BackendLifecycle | null> {
  if (!isTauri) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<BackendLifecycle>("restart_backend");
}

export function loadWebDefaultModel(): string | null {
  return loadMigratedStorageValue(DEFAULT_MODEL_STORAGE_KEY, LEGACY_DEFAULT_MODEL_STORAGE_KEY);
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

export function loadWebAutosaveMarkdownDir(): string | null {
  return loadMigratedStorageValue(
    AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY,
    LEGACY_AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY
  );
}

export async function saveAutosaveMarkdownDir(
  dir: string | null,
  isTauri: boolean
): Promise<string | null> {
  const normalized = normalizeOptionalValue(dir);
  if (isTauri) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<string | null>("set_autosave_markdown_dir", { dir: normalized });
  }
  if (normalized) {
    storage()?.setItem(AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY, normalized);
  } else {
    storage()?.removeItem(AUTOSAVE_MARKDOWN_DIR_STORAGE_KEY);
  }
  return normalized;
}

export async function chooseAutosaveMarkdownDir(isTauri: boolean): Promise<string | null> {
  if (!isTauri) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({ directory: true, multiple: false });
  return typeof selected === "string" ? selected : null;
}

export async function chooseMediaPaths(isTauri: boolean): Promise<string[]> {
  if (!isTauri) return [];
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    multiple: true,
    directory: false,
    filters: [{
      name: "Аудио и видео",
      extensions: ["mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "mov", "mkv", "avi", "webm"]
    }]
  });
  return typeof selected === "string" ? [selected] : selected ?? [];
}

export async function isRegularFilePath(path: string, isTauri: boolean): Promise<boolean> {
  if (!isTauri) return false;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("is_regular_file_path", { path });
}

export async function openSavedMarkdownPath(path: string, isTauri: boolean): Promise<void> {
  if (!isTauri) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("open_saved_markdown", { path });
}

export async function revealSavedMarkdownPath(path: string, isTauri: boolean): Promise<void> {
  if (!isTauri) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("reveal_saved_markdown", { path });
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

function loadMigratedStorageValue(key: string, legacyKey: string): string | null {
  const currentStorage = storage();
  const value = normalizeOptionalValue(currentStorage?.getItem(key));
  if (value) return value;
  const legacyValue = normalizeOptionalValue(currentStorage?.getItem(legacyKey));
  if (legacyValue) currentStorage?.setItem(key, legacyValue);
  return legacyValue;
}
