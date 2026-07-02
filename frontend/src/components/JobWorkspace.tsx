import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  FolderOpen,
  ListChecks,
  ShieldCheck,
  Users
} from "lucide-react";
import type { ApiClient } from "../api";
import { formatBytes, formatSeconds } from "../format";
import type { Artifact, FinalMarkdownStatus, Job, JobEvent, SpeakerReviewPayload, TranscriptSegment, WordToken } from "../types";
import {
  artifactDisplayName,
  compareArtifactsForDisplay,
  currentMessage,
  currentProgress,
  currentProgressLabel,
  elapsedText,
  eventDisplayMessage,
  eventDisplayStatus,
  isRawRuntimeDetail,
  jobDisplayTitle,
  languageLabel,
  statusLabel,
  type SpeakerTurn
} from "../appViewModel";

interface JobWorkspaceProps {
  artifacts: Artifact[];
  autosaveMarkdownDir: string | null;
  client: ApiClient;
  events: JobEvent[];
  finalMarkdownStatus: FinalMarkdownStatus | null;
  isSelectedJobQuiet: boolean;
  isSavingFinalMarkdown: boolean;
  notice: string | null;
  now: number;
  selectedDiarizationDiagnostic: string | null;
  selectedDisplayWarnings: string[];
  selectedJob: Job | null;
  selectedJobDisplayStatus: string | null;
  selectedLastEventTime: number | null;
  selectedSpeakerTurns: SpeakerTurn[];
  speakerReview: SpeakerReviewPayload | null;
  onChooseFinalMarkdownFolder: () => void;
  onOpenFinalMarkdown: () => void;
  onSaveFinalMarkdownAgain: () => void;
  onSaveSpeakerAssignments: (assignments: Record<string, string>) => void;
  onSkipSpeakerAssignments: (assignments: Record<string, string>) => void;
}

export function JobWorkspace({
  artifacts,
  autosaveMarkdownDir,
  client,
  events,
  finalMarkdownStatus,
  isSelectedJobQuiet,
  isSavingFinalMarkdown,
  notice,
  now,
  selectedDiarizationDiagnostic,
  selectedDisplayWarnings,
  selectedJob,
  selectedJobDisplayStatus,
  selectedLastEventTime,
  selectedSpeakerTurns,
  speakerReview,
  onChooseFinalMarkdownFolder,
  onOpenFinalMarkdown,
  onSaveFinalMarkdownAgain,
  onSaveSpeakerAssignments,
  onSkipSpeakerAssignments
}: JobWorkspaceProps) {
  return (
    <>
      {selectedJob && (
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Задача</p>
            <h2>{jobDisplayTitle(selectedJob)}</h2>
          </div>
          <span className={`status-pill large ${selectedJobDisplayStatus ?? selectedJob.status}`}>
            {statusLabel(selectedJobDisplayStatus ?? selectedJob.status)}
          </span>
        </header>
      )}

      {selectedJob && (
        <>
          <section className={`progress-panel ${selectedJobDisplayStatus ?? selectedJob.status}`}>
            <div className="progress-copy">
              <div>
                <span className="progress-kicker">Сейчас</span>
                <strong>{currentMessage(selectedJob)}</strong>
              </div>
              <span className="progress-percent">{currentProgressLabel(selectedJob)}</span>
            </div>
            <div className="progress-track" aria-label="Прогресс обработки">
              <div style={{ width: `${currentProgress(selectedJob)}%` }} />
            </div>
            <div className="progress-meta">
              <span>{languageLabel(selectedJob)}</span>
              {selectedLastEventTime !== null && (
                <span>последнее событие {elapsedText(now - selectedLastEventTime)} назад</span>
              )}
            </div>
            {isSelectedJobQuiet && (
              <p className="stalled-note">
                Новых событий давно нет. Сейчас задача находится в долгом шаге ASR: модель может
                загружаться или распознавать длинный файл. Подробности пишутся в job.log.
              </p>
            )}
          </section>

          {notice && <div className="notice">{notice}</div>}

          <div className="content-grid">
            <TranscriptPane turns={selectedSpeakerTurns} />
            <aside className="detail-pane">
              <SpeakerReviewPanel
                isSaving={isSavingFinalMarkdown}
                review={speakerReview}
                onSave={onSaveSpeakerAssignments}
                onSkip={onSkipSpeakerAssignments}
              />
              <ProcessPanel events={events} selectedJob={selectedJob} />
              <DiagnosticsPanel
                isSelectedJobQuiet={isSelectedJobQuiet}
                selectedDiarizationDiagnostic={selectedDiarizationDiagnostic}
                selectedDisplayWarnings={selectedDisplayWarnings}
              />
              <FinalMarkdownPanel
                autosaveMarkdownDir={autosaveMarkdownDir}
                finalMarkdownStatus={finalMarkdownStatus}
                isSaving={isSavingFinalMarkdown}
                selectedJob={selectedJob}
                onChooseFolder={onChooseFinalMarkdownFolder}
                onOpenFile={onOpenFinalMarkdown}
                onSaveAgain={onSaveFinalMarkdownAgain}
              />
              <ArtifactsPanel artifacts={artifacts} client={client} />
            </aside>
          </div>
        </>
      )}

      {!selectedJob && notice && <div className="notice">{notice}</div>}

      {!selectedJob && (
        <section className="empty-workspace">
          <FileText size={26} />
          <strong>Здесь появится готовая расшифровка</strong>
          <p>Пока главный экран свободен: выберите запись выше и нажмите одну основную кнопку запуска.</p>
          <div className="empty-flow-hint">
            <span>Файл</span>
            <span>→</span>
            <span>Проверка спикеров</span>
            <span>→</span>
            <span>Готовый Markdown</span>
          </div>
        </section>
      )}
    </>
  );
}

function TranscriptPane({ turns }: { turns: SpeakerTurn[] }) {
  return (
    <section className="transcript-pane">
      <div className="pane-title">
        <Activity size={18} />
        <h3>Транскрипт</h3>
      </div>
      <div className="segments">
        {turns.map((turn) => (
          <article className="speaker-turn" key={turn.id}>
            <header>
              <b>{turn.speakerLabel}</b>
              <time>
                {formatSeconds(turn.start_seconds)} - {formatSeconds(turn.end_seconds)}
              </time>
            </header>
            <div>
              {turn.segments.map((segment, index) => (
                <p key={`${turn.id}-${index}`}>{renderSegmentText(segment)}</p>
              ))}
            </div>
          </article>
        ))}
        {turns.length === 0 && <div className="empty-state">Транскрипт пока не готов</div>}
      </div>
    </section>
  );
}

function renderSegmentText(segment: TranscriptSegment) {
  const text = (segment.text_clean || segment.text_raw).trim();
  const words = segment.words ?? [];
  if (!words.some((word) => word.issues?.length)) return text;

  const visibleWords = words.filter((word) => word.text_clean !== "");
  return visibleWords.map((word, index) => {
    const displayText = word.text_clean || word.text;
    const issueSummary = word.issues?.map((issue) => issue.message || issue.code).join("; ");
    const className = word.issues?.length ? `word-token ${wordIssueClass(word)}` : "word-token";
    const suffix =
      index === visibleWords.length - 1 && needsTerminalPunctuation(text, displayText)
        ? text[text.length - 1]
        : "";
    return (
      <span className={className} key={`${word.start_seconds}-${index}`} title={issueSummary}>
        {displayText}
        {suffix}
        {index < visibleWords.length - 1 ? " " : ""}
      </span>
    );
  });
}

function wordIssueClass(word: WordToken): string {
  const severity = word.issues?.some((issue) => issue.severity === "warning")
    ? "word-token-warning"
    : "word-token-info";
  return severity;
}

function needsTerminalPunctuation(text: string, lastWord: string): boolean {
  if (!text || !lastWord) return false;
  const terminal = text[text.length - 1];
  return [".", "!", "?", "…"].includes(terminal) && !lastWord.endsWith(terminal);
}


function SpeakerReviewPanel({
  isSaving,
  review,
  onSave,
  onSkip
}: {
  isSaving: boolean;
  review: SpeakerReviewPayload | null;
  onSave: (assignments: Record<string, string>) => void;
  onSkip: (assignments: Record<string, string>) => void;
}) {
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const groups = review?.groups ?? [];
  const isPending = review?.status === "pending";

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const group of groups) {
      next[group.machine_label] = group.display_label === group.fallback_label ? "" : group.display_label;
    }
    setAssignments(next);
  }, [review?.status, groups.map((group) => `${group.machine_label}:${group.display_label}`).join("|")]);

  if (!groups.length || review?.status === "not_required") return null;

  return (
    <section className={isPending ? "speaker-review-panel pending" : "speaker-review-panel"}>
      <div className="pane-title">
        <Users size={18} />
        <h3>Проверьте спикеров</h3>
      </div>
      <p className="speaker-review-help">
        Назначьте имена по примерным репликам. Если оставить пусто, в файле будет «Спикер 1», «Спикер 2».
      </p>
      <div className="speaker-review-list">
        {groups.map((group) => (
          <label className="speaker-review-row" key={group.machine_label}>
            <span>
              <strong>{group.fallback_label}</strong>
              {group.example && <small>“{group.example}”</small>}
            </span>
            <input
              list={`speaker-suggestions-${group.machine_label}`}
              placeholder={group.fallback_label}
              value={assignments[group.machine_label] ?? ""}
              onChange={(event) =>
                setAssignments((current) => ({
                  ...current,
                  [group.machine_label]: event.target.value
                }))
              }
            />
            <datalist id={`speaker-suggestions-${group.machine_label}`}>
              {group.suggestions.map((suggestion) => (
                <option key={suggestion} value={suggestion} />
              ))}
            </datalist>
          </label>
        ))}
      </div>
      <div className="speaker-review-actions">
        <button type="button" disabled={isSaving} onClick={() => onSave(assignments)}>
          {isSaving ? "Сохраняю…" : "Сохранить транскрипцию"}
        </button>
        <button type="button" disabled={isSaving} onClick={() => onSkip({})}>
          Пропустить и сохранить
        </button>
      </div>
    </section>
  );
}

function ProcessPanel({ events, selectedJob }: { events: JobEvent[]; selectedJob: Job }) {
  return (
    <section className="process-card">
      <div className="pane-title">
        <ListChecks size={18} />
        <h3>Процесс</h3>
      </div>
      <div className="event-list">
        {events.length ? (
          events.map((event, index) => (
            <article
              className={`event-row ${eventDisplayStatus(event, selectedJob)}`}
              key={`${event.timestamp}-${index}`}
            >
              <span>{event.progress}%</span>
              <div>
                <strong>{eventDisplayMessage(event, selectedJob)}</strong>
                <small>
                  {event.stage} · {event.timestamp}
                </small>
              </div>
            </article>
          ))
        ) : (
          <p>Событий пока нет</p>
        )}
      </div>
    </section>
  );
}

function DiagnosticsPanel({
  isSelectedJobQuiet,
  selectedDiarizationDiagnostic,
  selectedDisplayWarnings
}: {
  isSelectedJobQuiet: boolean;
  selectedDiarizationDiagnostic: string | null;
  selectedDisplayWarnings: string[];
}) {
  return (
    <section className="diagnostics-card">
      <div className="pane-title">
        {selectedDisplayWarnings.length ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
        <h3>{selectedDisplayWarnings.length ? "Нужна проверка" : "Проверки"}</h3>
      </div>
      <div className="warnings">
        {selectedDisplayWarnings.length ? (
          selectedDisplayWarnings.map((warning) =>
            isRawRuntimeDetail(warning) ? (
              <details className="technical-details" key={warning}>
                <summary>Технические детали ошибки</summary>
                <pre>{warning}</pre>
              </details>
            ) : (
              <p key={warning}>{warning}</p>
            )
          )
        ) : selectedDiarizationDiagnostic ? (
          <p>{selectedDiarizationDiagnostic}</p>
        ) : (
          <p>
            {isSelectedJobQuiet
              ? "Официальной ошибки нет, но задача давно не присылала новых событий."
              : "Предупреждений нет"}
          </p>
        )}
      </div>
    </section>
  );
}

function FinalMarkdownPanel({
  autosaveMarkdownDir,
  finalMarkdownStatus,
  isSaving,
  selectedJob,
  onChooseFolder,
  onOpenFile,
  onSaveAgain
}: {
  autosaveMarkdownDir: string | null;
  finalMarkdownStatus: FinalMarkdownStatus | null;
  isSaving: boolean;
  selectedJob: Job;
  onChooseFolder: () => void;
  onOpenFile: () => void;
  onSaveAgain: () => void;
}) {
  const savedPath = finalMarkdownStatus?.path ?? selectedJob.metadata.saved_markdown_path ?? null;
  const filename = finalMarkdownStatus?.filename ?? selectedJob.metadata.saved_markdown_filename ?? null;
  const missing = finalMarkdownStatus?.missing ?? selectedJob.metadata.saved_markdown_missing ?? false;
  const saved = Boolean(filename && !missing);
  const panelTone = missing ? "missing" : saved ? "saved" : "pending";
  const message = missing
    ? "Файл транскрипции не найден"
    : finalMarkdownStatus?.message ??
      selectedJob.metadata.saved_markdown_message ??
      (autosaveMarkdownDir ? "Готовый Markdown будет сохранён автоматически" : "Выберите папку для сохранения транскрипций");

  return (
    <section className={`final-markdown-card ${panelTone}`}>
      <div className="pane-title">
        {saved ? <CheckCircle2 size={18} /> : <FolderOpen size={18} />}
        <h3>{saved ? "Готовый Markdown" : "Сохранение Markdown"}</h3>
      </div>
      <div className="autosave-panel">
        <p>{message}</p>
        {autosaveMarkdownDir && <small>Папка: {autosaveMarkdownDir}</small>}
        {filename && !missing && <strong>Сохранено: {filename}</strong>}
        <div className="autosave-actions">
          <button type="button" onClick={onChooseFolder}>
            {autosaveMarkdownDir ? "Сменить папку" : "Выбрать папку"}
          </button>
          {savedPath && !missing && (
            <button type="button" onClick={onOpenFile}>
              Открыть файл
            </button>
          )}
          {missing && (
            <button type="button" disabled={isSaving} onClick={onSaveAgain}>
              {isSaving ? "Сохраняю…" : "Сохранить заново"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function ArtifactsPanel({ artifacts, client }: { artifacts: Artifact[]; client: ApiClient }) {
  return (
    <section className="artifacts-card">
      <div className="pane-title">
        <Download size={18} />
        <h3>Артефакты</h3>
      </div>
      <div className="artifact-list">
        {[...artifacts].sort(compareArtifactsForDisplay).map((artifact) => (
          <a
            className={artifact.name === "final_speech_text_md" ? "primary-artifact" : undefined}
            href={client.artifactUrl(artifact)}
            key={artifact.name}
          >
            <span>{artifactDisplayName(artifact)}</span>
            <small>{formatBytes(artifact.size_bytes)}</small>
          </a>
        ))}
        {artifacts.length === 0 && <p>Артефактов пока нет</p>}
      </div>
    </section>
  );
}
