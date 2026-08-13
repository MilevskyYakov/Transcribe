import { useEffect, useState } from "react";
import { AlertTriangle, Check, ExternalLink, FileText, FolderOpen, RotateCcw, Users } from "lucide-react";
import type { ApiClient } from "../api";
import { formatBytes, formatSeconds } from "../format";
import type { Artifact, FinalMarkdownStatus, Job, JobEvent, SpeakerReviewPayload } from "../types";
import {
  artifactDisplayName,
  compareArtifactsForDisplay,
  currentMessage,
  currentProgress,
  eventDisplayMessage,
  eventDisplayStatus,
  isActiveJob,
  isRawRuntimeDetail,
  jobDisplayTitle,
  type SpeakerTurn
} from "../appViewModel";

interface JobWorkspaceProps {
  artifacts: Artifact[];
  autosaveMarkdownDir: string | null;
  client: ApiClient;
  events: JobEvent[];
  finalMarkdownStatus: FinalMarkdownStatus | null;
  isSavingFinalMarkdown: boolean;
  notice: string | null;
  selectedDiarizationDiagnostic: string | null;
  selectedDiarizationTechnicalDiagnostic: string | null;
  selectedDisplayWarnings: string[];
  selectedJob: Job;
  selectedJobDisplayStatus: string;
  selectedSpeakerTurns: SpeakerTurn[];
  speakerReview: SpeakerReviewPayload | null;
  onChooseFinalMarkdownFolder: () => void;
  onNewTranscription: () => void;
  onOpenFinalMarkdown: () => void;
  onSaveFinalMarkdownAgain: () => void;
  onSaveSpeakerAssignments: (assignments: Record<string, string>) => void;
  onShowInFinder: () => void;
  onSkipSpeakerAssignments: (assignments: Record<string, string>) => void;
}

export function JobWorkspace({
  artifacts,
  autosaveMarkdownDir,
  client,
  events,
  finalMarkdownStatus,
  isSavingFinalMarkdown,
  notice,
  selectedDiarizationDiagnostic,
  selectedDiarizationTechnicalDiagnostic,
  selectedDisplayWarnings,
  selectedJob,
  selectedJobDisplayStatus,
  selectedSpeakerTurns,
  speakerReview,
  onChooseFinalMarkdownFolder,
  onNewTranscription,
  onOpenFinalMarkdown,
  onSaveFinalMarkdownAgain,
  onSaveSpeakerAssignments,
  onShowInFinder,
  onSkipSpeakerAssignments
}: JobWorkspaceProps) {
  if (isActiveJob(selectedJob)) {
    return (
      <ProcessingScreen
        events={events}
        job={selectedJob}
        notice={notice}
      />
    );
  }

  if (selectedJobDisplayStatus === "failed" || selectedJobDisplayStatus === "failed_partial") {
    return (
      <ErrorScreen
        events={events}
        job={selectedJob}
        warnings={selectedDisplayWarnings}
        onNewTranscription={onNewTranscription}
      />
    );
  }

  return (
    <ResultScreen
      artifacts={artifacts}
      autosaveMarkdownDir={autosaveMarkdownDir}
      client={client}
      events={events}
      finalMarkdownStatus={finalMarkdownStatus}
      isSaving={isSavingFinalMarkdown}
      job={selectedJob}
      notice={notice}
      diarizationDiagnostic={selectedDiarizationDiagnostic}
      diarizationTechnicalDiagnostic={selectedDiarizationTechnicalDiagnostic}
      speakerReview={speakerReview}
      turns={selectedSpeakerTurns}
      warnings={selectedDisplayWarnings}
      onChooseFolder={onChooseFinalMarkdownFolder}
      onNewTranscription={onNewTranscription}
      onOpenFile={onOpenFinalMarkdown}
      onSaveAgain={onSaveFinalMarkdownAgain}
      onSaveSpeakerAssignments={onSaveSpeakerAssignments}
      onShowInFinder={onShowInFinder}
      onSkipSpeakerAssignments={onSkipSpeakerAssignments}
    />
  );
}

function ProcessingScreen({ events, job, notice }: { events: JobEvent[]; job: Job; notice: string | null }) {
  const progress = currentProgress(job);
  return (
    <section className="processing-screen">
      <header className="screen-header job-heading">
        <div><p className="eyebrow">Обрабатывается</p><h1>{jobDisplayTitle(job)}</h1></div>
        <span className="status-label processing">Обработка</span>
      </header>
      <div className="processing-field">
        <span className="editorial-cut" aria-hidden="true" />
        <strong className="progress-number">{progress}%</strong>
        <div><p>{currentMessage(job)}</p><div className="progress-track"><span style={{ width: `${progress}%` }} /></div></div>
      </div>
      <p className="background-note">Можно открыть другую запись — обработка продолжится в фоне.</p>
      {notice && <p className="notice">{notice}</p>}
      <details className="secondary-details"><summary>Дополнительно</summary><EventList events={events} job={job} /></details>
    </section>
  );
}

function ErrorScreen({ events, job, warnings, onNewTranscription }: { events: JobEvent[]; job: Job; warnings: string[]; onNewTranscription: () => void }) {
  return (
    <section className="error-screen">
      <header className="screen-header job-heading">
        <div><p className="eyebrow">Ошибка задачи</p><h1>{jobDisplayTitle(job)}</h1></div>
        <span className="status-label failed"><AlertTriangle size={14} /> Не удалось обработать</span>
      </header>
      <div className="error-state">
        <AlertTriangle size={28} />
        <h2>Обработка остановилась</h2>
        <p>Создайте новую транскрипцию и выберите запись повторно. Остальные фоновые задачи продолжат работу.</p>
        <button className="primary-button" type="button" onClick={onNewTranscription}><RotateCcw size={17} /> Повторить с файлом</button>
      </div>
      <details className="secondary-details"><summary>Технические детали</summary><WarningList warnings={warnings} /><EventList events={events} job={job} /></details>
    </section>
  );
}

function ResultScreen({
  artifacts,
  autosaveMarkdownDir,
  client,
  events,
  finalMarkdownStatus,
  isSaving,
  job,
  notice,
  diarizationDiagnostic,
  diarizationTechnicalDiagnostic,
  speakerReview,
  turns,
  warnings,
  onChooseFolder,
  onNewTranscription,
  onOpenFile,
  onSaveAgain,
  onSaveSpeakerAssignments,
  onShowInFinder,
  onSkipSpeakerAssignments
}: {
  artifacts: Artifact[];
  autosaveMarkdownDir: string | null;
  client: ApiClient;
  events: JobEvent[];
  finalMarkdownStatus: FinalMarkdownStatus | null;
  isSaving: boolean;
  job: Job;
  notice: string | null;
  diarizationDiagnostic: string | null;
  diarizationTechnicalDiagnostic: string | null;
  speakerReview: SpeakerReviewPayload | null;
  turns: SpeakerTurn[];
  warnings: string[];
  onChooseFolder: () => void;
  onNewTranscription: () => void;
  onOpenFile: () => void;
  onSaveAgain: () => void;
  onSaveSpeakerAssignments: (assignments: Record<string, string>) => void;
  onShowInFinder: () => void;
  onSkipSpeakerAssignments: (assignments: Record<string, string>) => void;
}) {
  const savedPath = finalMarkdownStatus?.path ?? job.metadata.saved_markdown_path ?? null;
  const filename = finalMarkdownStatus?.filename ?? job.metadata.saved_markdown_filename ?? null;
  const missing = finalMarkdownStatus?.missing ?? job.metadata.saved_markdown_missing ?? false;
  const needsSpeakerReview = speakerReview?.status === "pending" && Boolean(speakerReview.groups.length);

  return (
    <section className="result-screen">
      <header className="screen-header job-heading">
        <div><p className="eyebrow">Результат</p><h1>{jobDisplayTitle(job)}</h1></div>
        <span className={warnings.length ? "status-label warning" : "status-label completed"}><Check size={14} /> {warnings.length ? "Готово с предупреждением" : "Готово"}</span>
      </header>

      {job.metadata.diarization_confidence?.mode === "transcript_without_labels" && diarizationDiagnostic && (
        <p className="notice">{diarizationDiagnostic}</p>
      )}

      {needsSpeakerReview && (
        <SpeakerReviewPanel
          isSaving={isSaving}
          review={speakerReview}
          onSave={onSaveSpeakerAssignments}
          onSkip={onSkipSpeakerAssignments}
        />
      )}

      <section className={missing ? "result-file missing" : "result-file"}>
        <FileText size={30} />
        <div><strong>{filename ?? `${jobDisplayTitle(job)}.md`}</strong><p>{missing ? "Файл не найден" : savedPath ?? autosaveMarkdownDir ?? "Markdown готовится"}</p></div>
      </section>

      {!needsSpeakerReview && (
        <div className="result-actions">
          {missing ? (
            <button className="primary-button" disabled={isSaving} type="button" onClick={onSaveAgain}>{isSaving ? "Сохраняю…" : "Сохранить заново"}</button>
          ) : (
            <button className="primary-button" disabled={!savedPath} type="button" onClick={onOpenFile}><ExternalLink size={17} /> Открыть Markdown</button>
          )}
          <button className="secondary-button" disabled={!savedPath || missing} type="button" onClick={onShowInFinder}><FolderOpen size={17} /> Показать в Finder</button>
          <button className="text-button" type="button" onClick={onNewTranscription}>Новая транскрипция</button>
          {missing && <button className="text-button" type="button" onClick={onChooseFolder}>Изменить папку</button>}
        </div>
      )}

      {notice && <p className="notice">{notice}</p>}
      {turns.length > 0 && <TranscriptPreview turns={turns} />}
      <details className="secondary-details">
        <summary>Дополнительно</summary>
        <div className="details-grid">
          <section><h2>Процесс</h2><EventList events={events} job={job} /></section>
          <section><h2>Диагностика</h2>{diarizationTechnicalDiagnostic && <p>{diarizationTechnicalDiagnostic}</p>}<WarningList warnings={warnings} /></section>
          <section><h2>Артефакты</h2><ArtifactList artifacts={artifacts} client={client} /></section>
        </div>
      </details>
    </section>
  );
}

function TranscriptPreview({ turns }: { turns: SpeakerTurn[] }) {
  return (
    <section className="transcript-preview">
      <h2>Транскрипция</h2>
      {turns.map((turn) => (
        <article key={turn.id}>
          <header>{turn.speakerLabel && <strong>{turn.speakerLabel}</strong>}<time>{formatSeconds(turn.start_seconds)}</time></header>
          <p>{turn.texts.join(" ")}</p>
        </article>
      ))}
    </section>
  );
}

function SpeakerReviewPanel({ isSaving, review, onSave, onSkip }: { isSaving: boolean; review: SpeakerReviewPayload; onSave: (assignments: Record<string, string>) => void; onSkip: (assignments: Record<string, string>) => void }) {
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  useEffect(() => {
    setAssignments(Object.fromEntries(review.groups.map((group) => [group.machine_label, group.display_label === group.fallback_label ? "" : group.display_label])));
  }, [review]);

  return (
    <section className="speaker-review-panel">
      <header><Users size={19} /><div><h2>Проверьте подписи спикеров</h2><p>Только для уверенно разделённых голосов.</p></div></header>
      <div className="speaker-review-list">
        {review.groups.map((group) => (
          <label key={group.machine_label}><span>{group.fallback_label}<small>{group.example}</small></span><input placeholder={group.fallback_label} value={assignments[group.machine_label] ?? ""} onChange={(event) => setAssignments((current) => ({ ...current, [group.machine_label]: event.target.value }))} /></label>
        ))}
      </div>
      <div className="review-actions"><button className="primary-button" disabled={isSaving} type="button" onClick={() => onSave(assignments)}>{isSaving ? "Сохраняю…" : "Сохранить транскрипцию"}</button><button className="text-button" disabled={isSaving} type="button" onClick={() => onSkip({})}>Без имён</button></div>
    </section>
  );
}

function EventList({ events, job }: { events: JobEvent[]; job: Job }) {
  if (!events.length) return <p className="empty-copy">Событий пока нет</p>;
  return <div className="event-list">{events.map((event, index) => <div className={`event-row ${eventDisplayStatus(event, job)}`} key={`${event.timestamp}-${index}`}><span>{event.progress}%</span><div><strong>{eventDisplayMessage(event, job)}</strong><small>{event.stage}</small></div></div>)}</div>;
}

function WarningList({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return <p className="empty-copy">Предупреждений нет</p>;
  return <div className="warning-list">{warnings.map((warning) => isRawRuntimeDetail(warning) ? <pre key={warning}>{warning}</pre> : <p key={warning}>{warning}</p>)}</div>;
}

function ArtifactList({ artifacts, client }: { artifacts: Artifact[]; client: ApiClient }) {
  if (!artifacts.length) return <p className="empty-copy">Артефактов нет</p>;
  return <div className="artifact-list">{[...artifacts].sort(compareArtifactsForDisplay).map((artifact) => <a href={client.artifactUrl(artifact)} key={artifact.name}><span>{artifactDisplayName(artifact)}</span><small>{formatBytes(artifact.size_bytes)}</small></a>)}</div>;
}