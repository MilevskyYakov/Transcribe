import { FileText, RefreshCw, Server, Settings, SlidersHorizontal } from "lucide-react";
import type { BackendLifecycle, Job } from "../types";
import {
  backendLifecycleLabel,
  backendLifecycleTone,
  displayStatus,
  jobDisplayTitle,
  languageLabel,
  statusLabel
} from "../appViewModel";

interface AppSidebarProps {
  apiBase: string;
  backendLifecycle: BackendLifecycle | null;
  batchPaths: string;
  cacheDir: string | null;
  ffmpegAvailable: boolean;
  ffprobeAvailable: boolean;
  health: "unknown" | "ok" | "down";
  isManagedApp: boolean;
  isSubmitting: boolean;
  jobs: Job[];
  outputDir: string | null;
  selectedJobId: string | null;
  selectedModelTitle: string;
  watchFolder: string;
  onApiBaseChange: (value: string) => void;
  onBatchPathsChange: (value: string) => void;
  onModelsOpen: () => void;
  onRefresh: () => void;
  onRetryBackendStart: () => void;
  onSelectJob: (jobId: string) => void;
  onCleanupTemp: () => void;
  onSubmitBatch: () => void;
  onSubmitWatchScan: () => void;
  onWatchFolderChange: (value: string) => void;
}

export function AppSidebar({
  apiBase,
  backendLifecycle,
  batchPaths,
  cacheDir,
  ffmpegAvailable,
  ffprobeAvailable,
  health,
  isManagedApp,
  isSubmitting,
  jobs,
  outputDir,
  selectedJobId,
  selectedModelTitle,
  watchFolder,
  onApiBaseChange,
  onBatchPathsChange,
  onModelsOpen,
  onRefresh,
  onRetryBackendStart,
  onSelectJob,
  onCleanupTemp,
  onSubmitBatch,
  onSubmitWatchScan,
  onWatchFolderChange
}: AppSidebarProps) {
  const lifecycleTone = backendLifecycleTone(backendLifecycle);
  const lifecycleLabel = backendLifecycleLabel(backendLifecycle);
  const technicalDetails = [
    `state: ${backendLifecycle?.state ?? health}`,
    `api: ${apiBase}`,
    backendLifecycle?.last_check_at ? `last_check_at: ${backendLifecycle.last_check_at}` : null,
    backendLifecycle?.technical_detail ? `detail: ${backendLifecycle.technical_detail}` : null,
    ...(backendLifecycle?.recent_output ?? [])
  ].filter(Boolean);

  return (
    <aside className="job-rail">
      <div className="brand-block">
        <FileText size={24} />
        <div>
          <h1>Транскрибация</h1>
          <p>Локальная панель</p>
        </div>
      </div>

      <section className="app-status-panel" aria-label="Статус приложения">
        <div className={`status-tile ${lifecycleTone}`}>
          <Server size={16} />
          <span>Backend</span>
          <strong>{lifecycleLabel}</strong>
          {backendLifecycle?.state === "error" && (
            <button className="inline-status-action" type="button" onClick={onRetryBackendStart}>
              Повторить запуск
            </button>
          )}
        </div>
        <div className={ffmpegAvailable && ffprobeAvailable ? "status-tile ok" : "status-tile warn"}>
          <Settings size={16} />
          <span>Media tools</span>
          <strong>{ffmpegAvailable && ffprobeAvailable ? "ready" : "missing"}</strong>
        </div>
      </section>

      <section className="default-model-card">
        <div>
          <span>Модель по умолчанию</span>
          <strong>{selectedModelTitle}</strong>
        </div>
        <button className="secondary-action" type="button" onClick={onModelsOpen}>
          <SlidersHorizontal size={16} />
          <span>Модели</span>
        </button>
      </section>

      <details className="connection-details">
        <summary>Показать диагностику</summary>
        <p className="diagnostic-summary">
          {backendLifecycle?.state === "error"
            ? backendLifecycle.technical_detail || "Backend не запустился. Попробуйте повторить запуск."
            : backendLifecycle?.human_message || lifecycleLabel}
        </p>
        <div className="status-row compact">
          <span className={`service-dot ${lifecycleTone}`} />
          <input
            aria-label="Адрес локального API"
            value={apiBase}
            readOnly={isManagedApp}
            onChange={(event) => onApiBaseChange(event.target.value)}
          />
          <button className="icon-button" type="button" onClick={onRefresh}>
            <RefreshCw size={16} />
          </button>
        </div>
        <pre className="backend-diagnostics">{technicalDetails.join("\n")}</pre>
        <dl>
          <dt>Data</dt>
          <dd>{outputDir ?? "local output"}</dd>
          {cacheDir && (
            <>
              <dt>Model cache</dt>
              <dd>{cacheDir}</dd>
            </>
          )}
        </dl>
      </details>

      <details className="advanced-panel">
        <summary>Пакетная обработка и папка</summary>
        <section className="orchestration-panel">
          <textarea
            aria-label="Пути файлов для пакетной обработки"
            placeholder="Пути файлов для пакетной обработки"
            value={batchPaths}
            onChange={(event) => onBatchPathsChange(event.target.value)}
          />
          <button
            className="secondary-action"
            disabled={!batchPaths.trim() || isSubmitting}
            type="button"
            onClick={onSubmitBatch}
          >
            Запустить пакет
          </button>
          <input
            aria-label="Путь watch folder"
            placeholder="Путь watch folder"
            value={watchFolder}
            onChange={(event) => onWatchFolderChange(event.target.value)}
          />
          <button
            className="secondary-action"
            disabled={!watchFolder.trim() || isSubmitting}
            type="button"
            onClick={onSubmitWatchScan}
          >
            Проверить папку
          </button>
          <button
            className="secondary-action"
            disabled={isSubmitting}
            type="button"
            onClick={onCleanupTemp}
          >
            Очистить временные файлы
          </button>
        </section>
      </details>

      <section className="jobs-list" aria-label="Задачи">
        <h2>История</h2>
        {jobs.map((job) => (
          <button
            className={job.job_id === selectedJobId ? "job-item active" : "job-item"}
            key={job.job_id}
            type="button"
            onClick={() => onSelectJob(job.job_id)}
          >
            <span className={`status-pill ${displayStatus(job)}`}>{statusLabel(displayStatus(job))}</span>
            <strong>{jobDisplayTitle(job)}</strong>
            <small>{languageLabel(job)}</small>
          </button>
        ))}
        {jobs.length === 0 && <p className="muted">Здесь появятся последние задачи.</p>}
      </section>
    </aside>
  );
}
