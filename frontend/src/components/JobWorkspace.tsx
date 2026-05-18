import { Activity, AlertTriangle, Download, FileText, ListChecks } from "lucide-react";
import type { ApiClient } from "../api";
import { formatBytes, formatSeconds } from "../format";
import type { Artifact, Job, JobEvent, TranscriptSegment, WordToken } from "../types";
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
  client: ApiClient;
  events: JobEvent[];
  isSelectedJobQuiet: boolean;
  notice: string | null;
  now: number;
  selectedDiarizationDiagnostic: string | null;
  selectedDisplayWarnings: string[];
  selectedJob: Job | null;
  selectedJobDisplayStatus: string | null;
  selectedLastEventTime: number | null;
  selectedSpeakerTurns: SpeakerTurn[];
}

export function JobWorkspace({
  artifacts,
  client,
  events,
  isSelectedJobQuiet,
  notice,
  now,
  selectedDiarizationDiagnostic,
  selectedDisplayWarnings,
  selectedJob,
  selectedJobDisplayStatus,
  selectedLastEventTime,
  selectedSpeakerTurns
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
          <section className="progress-panel">
            <div className="progress-copy">
              <strong>{currentMessage(selectedJob)}</strong>
              <span>{currentProgressLabel(selectedJob)}</span>
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
              <ProcessPanel events={events} selectedJob={selectedJob} />
              <DiagnosticsPanel
                isSelectedJobQuiet={isSelectedJobQuiet}
                selectedDiarizationDiagnostic={selectedDiarizationDiagnostic}
                selectedDisplayWarnings={selectedDisplayWarnings}
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
          <strong>Детали появятся после запуска</strong>
          <p>Прогресс, транскрипт, диагностика и артефакты не занимают главный экран до первой задачи.</p>
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

function ProcessPanel({ events, selectedJob }: { events: JobEvent[]; selectedJob: Job }) {
  return (
    <section>
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
    <section>
      <div className="pane-title">
        <AlertTriangle size={18} />
        <h3>Диагностика</h3>
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

function ArtifactsPanel({ artifacts, client }: { artifacts: Artifact[]; client: ApiClient }) {
  return (
    <section>
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
