import { FileText, RefreshCw, Server, Settings, SlidersHorizontal } from "lucide-react";
import type { Job } from "../types";
import { displayStatus, jobDisplayTitle, languageLabel, statusLabel } from "../appViewModel";

interface AppSidebarProps {
  apiBase: string;
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
  onSelectJob: (jobId: string) => void;
  onSubmitBatch: () => void;
  onSubmitWatchScan: () => void;
  onWatchFolderChange: (value: string) => void;
}

export function AppSidebar({
  apiBase,
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
  onSelectJob,
  onSubmitBatch,
  onSubmitWatchScan,
  onWatchFolderChange
}: AppSidebarProps) {
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
        <div className="status-tile">
          <Server size={16} />
          <span>Backend</span>
          <strong>{health === "ok" ? "online" : health === "down" ? "offline" : "checking"}</strong>
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
        <summary>Диагностика</summary>
        <div className="status-row compact">
          <span className={`service-dot ${health}`} />
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
