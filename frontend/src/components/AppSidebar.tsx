import { Circle, History, Plus, Search, Settings } from "lucide-react";
import { displayStatus, jobDisplayTitle, statusLabel } from "../appViewModel";
import type { BatchSession, Job } from "../types";

const mnemaLockup = new URL("../assets/mnema-lockup.svg", import.meta.url).href;

export type AppView = "new" | "history" | "settings" | "job" | "batch";

interface AppSidebarProps {
  currentView: AppView;
  batchSessions: BatchSession[];
  jobs: Job[];
  searchQuery: string;
  selectedJobId: string | null;
  selectedBatchSessionId: string | null;
  onNewTranscription: () => void;
  onOpenHistory: () => void;
  onOpenSettings: () => void;
  onSearchQueryChange: (value: string) => void;
  onSelectBatchSession: (sessionId: string) => void;
  onSelectJob: (jobId: string) => void;
}

export function AppSidebar({
  currentView,
  batchSessions,
  jobs,
  searchQuery,
  selectedJobId,
  selectedBatchSessionId,
  onNewTranscription,
  onOpenHistory,
  onOpenSettings,
  onSearchQueryChange,
  onSelectBatchSession,
  onSelectJob
}: AppSidebarProps) {
  const normalizedQuery = searchQuery.trim().toLocaleLowerCase("ru");
  const batchJobIds = new Set(
    batchSessions.flatMap((session) => session.items.flatMap((item) => item.attempt_job_ids))
  );
  const visibleSessions = batchSessions.filter((session) =>
    !normalizedQuery || session.items.some((item) => item.display_title.toLocaleLowerCase("ru").includes(normalizedQuery))
  );
  const visibleJobs = jobs
    .filter((job) => !batchJobIds.has(job.job_id))
    .filter((job) => !normalizedQuery || jobDisplayTitle(job).toLocaleLowerCase("ru").includes(normalizedQuery))
    .slice(0, Math.max(0, 12 - visibleSessions.length));

  return (
    <aside className="app-sidebar">
      <img className="brand-lockup" src={mnemaLockup} alt="Mnema" />

      <nav className="primary-nav" aria-label="Основная навигация">
        <button className={currentView === "new" ? "nav-item active" : "nav-item"} type="button" onClick={onNewTranscription}>
          <Plus size={18} />
          <span>Новая транскрипция</span>
        </button>
        <label className="sidebar-search">
          <Search size={16} />
          <input
            aria-label="Поиск по записям"
            placeholder="Поиск"
            value={searchQuery}
            onChange={(event) => {
              onSearchQueryChange(event.target.value);
              onOpenHistory();
            }}
          />
        </label>
      </nav>

      <section className="sidebar-history" aria-label="История">
        <button className="sidebar-heading" type="button" onClick={onOpenHistory}>
          <History size={15} />
          <span>История</span>
        </button>
        <div className="history-list">
          {visibleSessions.slice(0, 12).map((session) => (
            <button
              className={session.session_id === selectedBatchSessionId && currentView === "batch" ? "history-item active" : "history-item"}
              key={session.session_id}
              type="button"
              onClick={() => onSelectBatchSession(session.session_id)}
            >
              <Circle className={`history-status ${session.status === "active" ? "processing" : session.totals.failed ? "failed" : "completed"}`} fill="currentColor" size={8} />
              <span>
                <strong>Пакет · {session.totals.total} файлов</strong>
                <small>{session.status === "active" ? `Готово ${session.totals.ready} из ${session.totals.total}` : session.totals.failed ? `Готово ${session.totals.ready}, ошибок ${session.totals.failed}` : "Готово"}</small>
              </span>
            </button>
          ))}
          {visibleJobs.map((job) => {
            const status = displayStatus(job);
            return (
              <button
                className={job.job_id === selectedJobId && currentView === "job" ? "history-item active" : "history-item"}
                key={job.job_id}
                type="button"
                onClick={() => onSelectJob(job.job_id)}
              >
                <Circle className={`history-status ${status}`} fill="currentColor" size={8} />
                <span>
                  <strong>{jobDisplayTitle(job)}</strong>
                  <small>{statusLabel(status)}</small>
                </span>
              </button>
            );
          })}
          {visibleJobs.length === 0 && visibleSessions.length === 0 && <p className="sidebar-empty">Записей пока нет</p>}
        </div>
      </section>

      <button className={currentView === "settings" ? "settings-entry active" : "settings-entry"} type="button" onClick={onOpenSettings}>
        <Settings size={18} />
        <span>Настройки</span>
      </button>
    </aside>
  );
}