import { RefreshCw, Server, SlidersHorizontal, Wrench } from "lucide-react";
import {
  canRunUpdateAction,
  updateActionLabel,
  updateProgressLabel,
  updateStatusTone,
  type UpdateState
} from "../appUpdates";
import { backendLifecycleLabel, backendLifecycleTone } from "../appViewModel";
import type { BackendLifecycle } from "../types";

interface SettingsPanelProps {
  apiBase: string;
  autosaveMarkdownDir: string | null;
  backendLifecycle: BackendLifecycle | null;
  cacheDir: string | null;
  ffmpegAvailable: boolean;
  ffprobeAvailable: boolean;
  health: "unknown" | "ok" | "down";
  isManagedApp: boolean;
  isSubmitting: boolean;
  outputDir: string | null;
  selectedModelTitle: string;
  updateState: UpdateState;
  onApiBaseChange: (value: string) => void;
  onChooseFolder: () => void;
  onCleanupTemp: () => void;
  onDone: () => void;
  onModelsOpen: () => void;
  onRefresh: () => void;
  onRetryBackendStart: () => void;
  onUpdateAction: () => void;
}

export function SettingsPanel({
  apiBase,
  autosaveMarkdownDir,
  backendLifecycle,
  cacheDir,
  ffmpegAvailable,
  ffprobeAvailable,
  health,
  isManagedApp,
  isSubmitting,
  outputDir,
  selectedModelTitle,
  updateState,
  onApiBaseChange,
  onChooseFolder,
  onCleanupTemp,
  onDone,
  onModelsOpen,
  onRefresh,
  onRetryBackendStart,
  onUpdateAction
}: SettingsPanelProps) {
  const lifecycleTone = backendLifecycleTone(backendLifecycle);
  const technicalDetails = [
    `state: ${backendLifecycle?.state ?? health}`,
    `api: ${apiBase}`,
    backendLifecycle?.last_check_at ? `last_check_at: ${backendLifecycle.last_check_at}` : null,
    backendLifecycle?.technical_detail ? `detail: ${backendLifecycle.technical_detail}` : null,
    ...(backendLifecycle?.recent_output ?? [])
  ].filter(Boolean);

  return (
    <section className="settings-screen">
      <header className="screen-header">
        <div>
          <p className="eyebrow">Mnema</p>
          <h1>Настройки</h1>
        </div>
        <button className="primary-button compact" type="button" onClick={onDone}>Готово</button>
      </header>

      <div className="settings-sections">
        <section className="settings-section">
          <h2>Сохранение</h2>
          <div className="setting-row">
            <div><strong>Папка по умолчанию</strong><p>{autosaveMarkdownDir ?? "Не выбрана"}</p></div>
            <button className="secondary-button" type="button" onClick={onChooseFolder}>Изменить</button>
          </div>
        </section>

        <section className="settings-section">
          <h2>Распознавание</h2>
          <div className="setting-row">
            <div><strong>Модель по умолчанию</strong><p>{selectedModelTitle}</p></div>
            <button className="secondary-button" type="button" onClick={onModelsOpen}>
              <SlidersHorizontal size={16} /> Модели
            </button>
          </div>
        </section>

        <section className="settings-section">
          <h2>Обновления</h2>
          <div className={`setting-row update ${updateStatusTone(updateState.status)}`}>
            <div><strong>{updateState.version ? `Версия ${updateState.version}` : "Mnema для macOS"}</strong><p>{updateProgressLabel(updateState) ?? updateState.message}</p></div>
            <button className="secondary-button" disabled={!canRunUpdateAction(updateState, isManagedApp)} type="button" onClick={onUpdateAction}>
              {updateActionLabel(updateState, isManagedApp)}
            </button>
          </div>
        </section>

        <section className="settings-section">
          <h2>Диагностика</h2>
          <div className="diagnostic-grid">
            <div className={`diagnostic-tile ${lifecycleTone}`}><Server size={17} /><span>Backend</span><strong>{backendLifecycleLabel(backendLifecycle)}</strong></div>
            <div className={ffmpegAvailable && ffprobeAvailable ? "diagnostic-tile ok" : "diagnostic-tile warn"}><Wrench size={17} /><span>Media tools</span><strong>{ffmpegAvailable && ffprobeAvailable ? "Готовы" : "Не найдены"}</strong></div>
          </div>
          {backendLifecycle?.state === "error" && <button className="secondary-button" type="button" onClick={onRetryBackendStart}>Повторить запуск</button>}
          <details className="technical-details">
            <summary>Технические детали</summary>
            <div className="technical-body">
              <label>Локальный API<input value={apiBase} readOnly={isManagedApp} onChange={(event) => onApiBaseChange(event.target.value)} /></label>
              <button className="icon-button" aria-label="Обновить диагностику" type="button" onClick={onRefresh}><RefreshCw size={16} /></button>
              <pre>{technicalDetails.join("\n")}</pre>
              <dl><dt>Данные</dt><dd>{outputDir ?? "local output"}</dd><dt>Кэш моделей</dt><dd>{cacheDir ?? "local cache"}</dd></dl>
              <button className="secondary-button" disabled={isSubmitting} type="button" onClick={onCleanupTemp}>Очистить временные файлы</button>
            </div>
          </details>
        </section>

      </div>
    </section>
  );
}