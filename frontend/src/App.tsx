import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient, normalizeBaseUrl } from "./api";
import {
  chooseAutosaveMarkdownDir,
  loadBackendStatus,
  loadWebAutosaveMarkdownDir,
  loadWebDefaultModel,
  markBackendOffline,
  markBackendOnline,
  openSavedMarkdownPath,
  resolveAppEnvironment,
  restartBackend,
  saveAutosaveMarkdownDir,
  saveDefaultModel
} from "./appEnvironment";
import {
  checkForAppUpdate,
  initialUpdateState,
  isReleaseEndpointUnavailable,
  isUpdateFeedCheckFailure,
  reduceDownloadEvent,
  updateMessageForError,
  type PendingUpdate,
  type UpdateState
} from "./appUpdates";
import {
  canChooseModelAsDefault,
  canSubmitTranscriptionJob,
  canStartWithDefaultModel,
  DEFAULT_API_BASE,
  diarizationDiagnostic,
  displayStatus,
  displayWarnings,
  isActiveJob,
  jobDisplayTitle,
  lastEventTime,
  modelLabel,
  selectedJobDetailsRefreshKey,
  speakerTurns,
  titleValidationMessage,
  titleFromFilename
} from "./appViewModel";
import { AppSidebar } from "./components/AppSidebar";
import { JobWorkspace } from "./components/JobWorkspace";
import { ModelsModal } from "./components/ModelsModal";
import { UploadPanel } from "./components/UploadPanel";
import { formatBytes } from "./format";
import type {
  AppEnvironment,
  Artifact,
  BackendLifecycle,
  FinalMarkdownStatus,
  HealthPayload,
  Job,
  JobEvent,
  ModelsPayload,
  SpeakerReviewPayload,
  TranscriptSegment
} from "./types";

export {
  artifactDisplayName,
  canChooseModelAsDefault,
  canSubmitTranscriptionJob,
  canStartWithDefaultModel,
  compareArtifactsForDisplay,
  currentMessage,
  currentProgressLabel,
  backendLifecycleLabel,
  backendLifecycleTone,
  defaultModelActionLabel,
  diarizationDiagnostic,
  displayStatus,
  displayWarnings,
  eventDisplayMessage,
  eventDisplayStatus,
  eventMessageForTest,
  isDiarizationQualityWarning,
  isRawRuntimeDetail,
  jobDisplayTitle,
  modelDownloadActionLabel,
  selectedJobDetailsRefreshKey,
  speakerTurns,
  titleValidationMessage,
  titleFromFilename,
  type SpeakerTurn
} from "./appViewModel";
export {
  canRunUpdateAction,
  initialUpdateState,
  isReleaseEndpointUnavailable,
  isUpdateFeedCheckFailure,
  reduceDownloadEvent,
  updateActionLabel,
  updateProgressLabel,
  updateStatusTone
} from "./appUpdates";

export function App() {
  const [apiBase, setApiBase] = useState(
    () => localStorage.getItem("transcribe-doc-api-base") ?? DEFAULT_API_BASE
  );
  const [appEnvironment, setAppEnvironment] = useState<AppEnvironment | null>(null);
  const [backendLifecycle, setBackendLifecycle] = useState<BackendLifecycle | null>(null);
  const [, setBackendHealthFailures] = useState(0);
  const [health, setHealth] = useState<"unknown" | "ok" | "down">("unknown");
  const [healthDetails, setHealthDetails] = useState<HealthPayload | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [transcriptionTitle, setTranscriptionTitle] = useState("");
  const [speakerHint, setSpeakerHint] = useState("");
  const [selectedModelName, setSelectedModelName] = useState(() => loadWebDefaultModel() ?? "large-v3");
  const [autosaveMarkdownDir, setAutosaveMarkdownDir] = useState(() => loadWebAutosaveMarkdownDir());
  const [finalMarkdownStatus, setFinalMarkdownStatus] = useState<FinalMarkdownStatus | null>(null);
  const [speakerReview, setSpeakerReview] = useState<SpeakerReviewPayload | null>(null);
  const [isSavingFinalMarkdown, setIsSavingFinalMarkdown] = useState(false);
  const [isModelsOpen, setIsModelsOpen] = useState(false);
  const [batchPaths, setBatchPaths] = useState("");
  const [watchFolder, setWatchFolder] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const [updateState, setUpdateState] = useState<UpdateState>(initialUpdateState);
  const [pendingUpdate, setPendingUpdate] = useState<PendingUpdate | null>(null);

  const client = useMemo(() => new ApiClient(normalizeBaseUrl(apiBase)), [apiBase]);
  const selectedJob = jobs.find((job) => job.job_id === selectedJobId) ?? null;
  const selectedJobDisplayStatus = selectedJob ? displayStatus(selectedJob) : null;
  const selectedDisplayWarnings = selectedJob ? displayWarnings(selectedJob) : [];
  const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "processing");
  const selectedLastEventTime = lastEventTime(events);
  const secondsSinceLastEvent =
    selectedLastEventTime === null ? null : Math.floor((now - selectedLastEventTime) / 1000);
  const isSelectedJobQuiet =
    isActiveJob(selectedJob) && secondsSinceLastEvent !== null && secondsSinceLastEvent >= 60;
  const hasModelDownload = models?.models.some((model) => model.status === "downloading") ?? false;
  const selectedModel = models?.models.find((model) => model.name === selectedModelName) ?? null;
  const outputDir = appEnvironment?.outputDir ?? healthDetails?.app?.output_dir ?? null;
  const cacheDir = appEnvironment?.cacheDir ?? healthDetails?.app?.cache_dir ?? null;
  const ffmpegAvailable =
    appEnvironment?.ffmpegAvailable ?? healthDetails?.media_tools?.ffmpeg.available ?? false;
  const ffprobeAvailable =
    appEnvironment?.ffprobeAvailable ?? healthDetails?.media_tools?.ffprobe.available ?? false;
  const isManagedApp = appEnvironment?.isTauri ?? false;
  const selectedModelTitle = selectedModel?.label ?? selectedModel?.name ?? selectedModelName;
  const selectedModelIsReady = canStartWithDefaultModel(selectedModel);
  const selectedModelStatusText = selectedModel ? modelLabel(selectedModel) : "проверяю модели";
  const transcriptionTitleError = mediaFile ? titleValidationMessage(transcriptionTitle) : null;
  const canSubmitJob = canSubmitTranscriptionJob({
    mediaFile,
    transcriptionTitle,
    isSubmitting,
    selectedModelIsReady
  });
  const selectedJobRefreshKey = selectedJobDetailsRefreshKey(selectedJob);
  const selectedSpeakerTurns = useMemo(() => speakerTurns(segments), [segments]);
  const selectedDiarizationDiagnostic = diarizationDiagnostic(selectedJob);

  const refresh = useCallback(async () => {
    try {
      const nextHealth = await client.health();
      setHealth("ok");
      setHealthDetails(nextHealth);
      setBackendHealthFailures(0);
      const onlineLifecycle = await markBackendOnline(isManagedApp);
      if (onlineLifecycle) setBackendLifecycle(onlineLifecycle);
      const nextJobs = await client.listJobs();
      const nextModels = await client.listModels();
      setJobs(nextJobs);
      setModels(nextModels);
      setSelectedModelName((current) =>
        nextModels.models.some((model) => model.name === current) ? current : nextModels.current_model
      );
      setSelectedJobId((current) =>
        current && nextJobs.some((job) => job.job_id === current) ? current : null
      );
      setNotice(null);
    } catch (error) {
      setHealth("down");
      setHealthDetails(null);
      const message = error instanceof Error ? error.message : "Сервис недоступен";
      const offlineLifecycle = await markBackendOffline(isManagedApp, message);
      if (offlineLifecycle) {
        setBackendLifecycle(offlineLifecycle);
        setBackendHealthFailures((current) => {
          const next = current + 1;
          if (isManagedApp && next >= 3) {
            setBackendLifecycle({
              ...offlineLifecycle,
              state: "error",
              human_message: "Не удалось запустить",
              technical_detail: message
            });
          }
          return next;
        });
      }
      setNotice(message);
    }
  }, [client, isManagedApp]);

  useEffect(() => {
    let isActive = true;
    void resolveAppEnvironment(DEFAULT_API_BASE).then((environment) => {
      if (!isActive) return;
      setAppEnvironment(environment);
      setBackendLifecycle(environment.backendLifecycle ?? null);
      if (environment.isTauri) {
        setApiBase(environment.apiBaseUrl);
        if (environment.defaultModelName) {
          setSelectedModelName(environment.defaultModelName);
        }
        setAutosaveMarkdownDir(environment.autosaveMarkdownDir ?? null);
      }
    });
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (!isManagedApp) {
      localStorage.setItem("transcribe-doc-api-base", normalizeBaseUrl(apiBase));
    }
  }, [apiBase, isManagedApp]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!isManagedApp) return;
    const timer = window.setInterval(() => {
      void loadBackendStatus(true)
        .then((status) => {
          if (status) {
            setBackendLifecycle((current) =>
              current?.state === "error" && status.state !== "online" && status.state !== "restarting"
                ? current
                : status
            );
          }
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [isManagedApp]);

  useEffect(() => {
    if (!hasActiveJobs && !hasModelDownload) return;
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, hasModelDownload, refresh]);

  useEffect(() => {
    if (!isManagedApp) return;
    if (!["starting", "checking", "offline", "restarting"].includes(backendLifecycle?.state ?? "")) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [backendLifecycle?.state, isManagedApp, refresh]);

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs]);

  useEffect(() => {
    if (!selectedJobId) {
      setSegments([]);
      setArtifacts([]);
      setEvents([]);
      setFinalMarkdownStatus(null);
      setSpeakerReview(null);
      return;
    }
    let isActive = true;
    Promise.all([
      client.getTranscript(selectedJobId),
      client.listArtifacts(selectedJobId),
      client.listEvents(selectedJobId),
      client.finalMarkdownStatus(selectedJobId),
      client.speakerReview(selectedJobId)
    ])
      .then(([transcript, nextArtifacts, nextEvents, nextFinalMarkdownStatus, nextSpeakerReview]) => {
        if (!isActive) return;
        setSegments(transcript.segments);
        setArtifacts(nextArtifacts);
        setEvents(nextEvents);
        setFinalMarkdownStatus(nextFinalMarkdownStatus);
        setSpeakerReview(nextSpeakerReview);
      })
      .catch((error) => {
        if (isActive) setNotice(error instanceof Error ? error.message : "Задача недоступна");
      });
    return () => {
      isActive = false;
    };
  }, [client, selectedJobId, selectedJobRefreshKey]);

  useEffect(() => {
    if (!selectedJob || displayStatus(selectedJob) !== "completed") return;
    if (!speakerReview) return;
    if (speakerReview?.status === "pending") return;
    if (finalMarkdownStatus?.status === "saved" || finalMarkdownStatus?.status === "missing") return;
    if (!autosaveMarkdownDir) {
      setNotice("Выберите папку для сохранения транскрипций");
      return;
    }
    if (isSavingFinalMarkdown) return;
    void saveSelectedFinalMarkdown(autosaveMarkdownDir);
  }, [
    autosaveMarkdownDir,
    finalMarkdownStatus?.status,
    isSavingFinalMarkdown,
    selectedJob?.job_id,
    selectedJob?.status,
    speakerReview?.status
  ]);

  function handleMediaFileChange(file: File | null) {
    setMediaFile(file);
    setTranscriptionTitle(file ? titleFromFilename(file.name) : "");
  }

  async function submitJob(event: FormEvent) {
    event.preventDefault();
    if (!mediaFile) return;
    if (transcriptionTitleError) {
      setNotice(transcriptionTitleError);
      return;
    }
    if (!selectedModelIsReady) {
      setNotice("Выберите готовую модель распознавания или скачайте текущую модель.");
      setIsModelsOpen(true);
      return;
    }
    setIsSubmitting(true);
    try {
      const job = await client.createJob(
        mediaFile,
        transcriptionTitle,
        speakerHint,
        selectedModel?.backend,
        selectedModel?.name ?? selectedModelName
      );
      await refresh();
      setSelectedJobId(job?.job_id ?? null);
      setMediaFile(null);
      setTranscriptionTitle("");
      setNotice("Задача поставлена в очередь");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось запустить задачу");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitBatch() {
    const inputPaths = batchPaths
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!inputPaths.length) return;
    if (!selectedModelIsReady) {
      setNotice("Выберите готовую модель распознавания или скачайте текущую модель.");
      setIsModelsOpen(true);
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await client.createBatch(
        inputPaths,
        speakerHint,
        selectedModel?.backend,
        selectedModel?.name ?? selectedModelName
      );
      await refresh();
      setNotice(`Пакет завершён: успешно ${result.succeeded} из ${result.total}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Пакетная обработка не удалась");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitWatchScan() {
    if (!watchFolder.trim()) return;
    setIsSubmitting(true);
    try {
      const result = await client.scanWatchFolder(watchFolder.trim());
      await refresh();
      setNotice(`Папка проверена: успешно ${result.succeeded} из ${result.total}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Проверка папки не удалась");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function cleanupTemporaryFiles() {
    setIsSubmitting(true);
    try {
      const result = await client.cleanupTemporaryFiles();
      await refresh();
      setNotice(
        `Временные файлы очищены: ${result.removed_count}, освобождено ${formatBytes(result.freed_bytes)}`
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось очистить временные файлы");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startModelDownload(modelName: string) {
    try {
      const result = await client.downloadModel(modelName);
      await refresh();
      setNotice(result.message);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось запустить загрузку модели");
    }
  }

  async function startAllModelDownloads() {
    try {
      const result = await client.downloadAllModels();
      await refresh();
      setNotice(result.message);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось запустить загрузку моделей");
    }
  }

  async function retryBackendStart() {
    setNotice(null);
    setBackendHealthFailures(0);
    const restarting = await restartBackend(isManagedApp);
    if (restarting) {
      setBackendLifecycle(restarting);
      const environment = await resolveAppEnvironment(DEFAULT_API_BASE);
      setAppEnvironment(environment);
      setBackendLifecycle(environment.backendLifecycle ?? restarting);
      setApiBase(environment.apiBaseUrl);
      await refresh();
      return;
    }
    await refresh();
  }

  async function chooseDefaultModel(modelName: string) {
    const model = models?.models.find((item) => item.name === modelName) ?? null;
    if (!canChooseModelAsDefault(model)) {
      setNotice("Модель по умолчанию можно выбрать только после скачивания.");
      return;
    }
    try {
      const savedModelName = await saveDefaultModel(modelName, isManagedApp);
      setSelectedModelName(savedModelName);
      setAppEnvironment((current) => (current ? { ...current, defaultModelName: savedModelName } : current));
      setNotice(`Модель по умолчанию: ${savedModelName}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось сохранить модель");
    }
  }

  async function chooseFinalMarkdownFolder() {
    try {
      let selected = await chooseAutosaveMarkdownDir(isManagedApp);
      if (!selected && !isManagedApp) {
        selected = window.prompt("Папка для сохранения транскрипций", autosaveMarkdownDir ?? "");
      }
      if (!selected) return;
      const saved = await saveAutosaveMarkdownDir(selected, isManagedApp);
      setAutosaveMarkdownDir(saved);
      setAppEnvironment((current) => (current ? { ...current, autosaveMarkdownDir: saved } : current));
      setNotice(saved ? `Папка сохранения: ${saved}` : null);
      if (selectedJob && displayStatus(selectedJob) === "completed" && saved) {
        await saveSelectedFinalMarkdown(saved);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось выбрать папку сохранения");
    }
  }

  async function saveSelectedFinalMarkdown(dir = autosaveMarkdownDir) {
    if (!selectedJob) return;
    if (!dir) {
      setNotice("Выберите папку для сохранения транскрипций");
      return;
    }
    setIsSavingFinalMarkdown(true);
    try {
      const status = await client.saveFinalMarkdown(selectedJob.job_id, dir);
      setFinalMarkdownStatus(status);
      await refresh();
      setNotice(status.message);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось сохранить Markdown");
    } finally {
      setIsSavingFinalMarkdown(false);
    }
  }

  async function saveSpeakerAssignments(assignments: Record<string, string>, skipped = false) {
    if (!selectedJob) return;
    if (!autosaveMarkdownDir) {
      setNotice("Выберите папку для сохранения транскрипций");
      return;
    }
    setIsSavingFinalMarkdown(true);
    try {
      const result = await client.saveSpeakerReview(selectedJob.job_id, assignments, {
        skipped,
        autosaveDir: autosaveMarkdownDir
      });
      setSpeakerReview(result.speaker_review);
      if (result.final_markdown) setFinalMarkdownStatus(result.final_markdown);
      const transcript = await client.getTranscript(selectedJob.job_id);
      setSegments(transcript.segments);
      await refresh();
      setNotice(result.final_markdown?.message ?? "Имена спикеров сохранены");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось сохранить имена спикеров");
    } finally {
      setIsSavingFinalMarkdown(false);
    }
  }

  async function openFinalMarkdown() {
    const path = finalMarkdownStatus?.path ?? selectedJob?.metadata.saved_markdown_path ?? null;
    if (!path) return;
    try {
      await openSavedMarkdownPath(path, isManagedApp);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось открыть файл");
    }
  }

  async function handleUpdateAction() {
    if (!isManagedApp) {
      setUpdateState({ status: "error", message: "Обновление доступно только в установленном app." });
      return;
    }
    if (pendingUpdate) {
      setUpdateState((current) => ({
        ...current,
        status: "downloading",
        message: "Скачиваю и проверяю подписанное обновление…",
        downloadedBytes: 0,
        totalBytes: null
      }));
      try {
        await pendingUpdate.downloadAndInstall((event) => {
          setUpdateState((current) => reduceDownloadEvent(current, event));
        });
        setPendingUpdate(null);
        setUpdateState({
          status: "installed",
          version: pendingUpdate.version,
          currentVersion: pendingUpdate.currentVersion,
          message: "Обновление установлено. Перезапустите приложение, чтобы открыть новую версию."
        });
      } catch (error) {
        setUpdateState({
          status: "error",
          version: pendingUpdate.version,
          currentVersion: pendingUpdate.currentVersion,
          message: updateMessageForError(error)
        });
      }
      return;
    }

    setUpdateState({ status: "checking", message: "Проверяю release endpoint…" });
    try {
      const update = await checkForAppUpdate();
      if (!update) {
        setUpdateState({ status: "not-available", message: "Установлена последняя версия." });
        return;
      }
      setPendingUpdate(update);
      setUpdateState({
        status: "available",
        version: update.version,
        currentVersion: update.currentVersion,
        notes: update.notes,
        message: `Доступна версия ${update.version}. Обновление будет проверено подписью перед установкой.`
      });
    } catch (error) {
      if (isUpdateFeedCheckFailure(error)) {
        setUpdateState({ status: "not-available", message: updateMessageForError(error) });
        return;
      }
      setUpdateState({ status: "error", message: updateMessageForError(error) });
    }
  }

  return (
    <main className="app-shell">
      <AppSidebar
        apiBase={apiBase}
        batchPaths={batchPaths}
        cacheDir={cacheDir}
        ffmpegAvailable={ffmpegAvailable}
        ffprobeAvailable={ffprobeAvailable}
        health={health}
        backendLifecycle={backendLifecycle}
        isManagedApp={isManagedApp}
        isSubmitting={isSubmitting}
        jobs={jobs}
        outputDir={outputDir}
        selectedJobId={selectedJobId}
        selectedModelTitle={selectedModelTitle}
        updateState={updateState}
        watchFolder={watchFolder}
        onApiBaseChange={setApiBase}
        onBatchPathsChange={setBatchPaths}
        onModelsOpen={() => setIsModelsOpen(true)}
        onRefresh={() => void refresh()}
        onRetryBackendStart={() => void retryBackendStart()}
        onSelectJob={setSelectedJobId}
        onUpdateAction={() => void handleUpdateAction()}
        onCleanupTemp={() => void cleanupTemporaryFiles()}
        onSubmitBatch={() => void submitBatch()}
        onSubmitWatchScan={() => void submitWatchScan()}
        onWatchFolderChange={setWatchFolder}
      />

      <section className="workspace">
        <UploadPanel
          canSubmitJob={canSubmitJob}
          isSubmitting={isSubmitting}
          mediaFile={mediaFile}
          selectedModelIsReady={selectedModelIsReady}
          selectedModelStatusText={selectedModelStatusText}
          selectedModelTitle={selectedModelTitle}
          speakerHint={speakerHint}
          titleError={transcriptionTitleError}
          transcriptionTitle={transcriptionTitle}
          onMediaFileChange={handleMediaFileChange}
          onSpeakerHintChange={setSpeakerHint}
          onSubmitJob={(event) => void submitJob(event)}
          onTranscriptionTitleChange={setTranscriptionTitle}
        />
        <JobWorkspace
          artifacts={artifacts}
          autosaveMarkdownDir={autosaveMarkdownDir}
          client={client}
          events={events}
          finalMarkdownStatus={finalMarkdownStatus}
          isSelectedJobQuiet={isSelectedJobQuiet}
          isSavingFinalMarkdown={isSavingFinalMarkdown}
          notice={notice}
          now={now}
          selectedDiarizationDiagnostic={selectedDiarizationDiagnostic}
          selectedDisplayWarnings={selectedDisplayWarnings}
          selectedJob={selectedJob}
          selectedJobDisplayStatus={selectedJobDisplayStatus}
          selectedLastEventTime={selectedLastEventTime}
          selectedSpeakerTurns={selectedSpeakerTurns}
          speakerReview={speakerReview}
          onChooseFinalMarkdownFolder={() => void chooseFinalMarkdownFolder()}
          onOpenFinalMarkdown={() => void openFinalMarkdown()}
          onSaveFinalMarkdownAgain={() => void saveSelectedFinalMarkdown()}
          onSaveSpeakerAssignments={(assignments) => void saveSpeakerAssignments(assignments, false)}
          onSkipSpeakerAssignments={(assignments) => void saveSpeakerAssignments(assignments, true)}
        />
      </section>

      {isModelsOpen && (
        <ModelsModal
          models={models}
          selectedModelName={selectedModelName}
          selectedModelTitle={selectedModelTitle}
          onChooseDefaultModel={(modelName) => void chooseDefaultModel(modelName)}
          onClose={() => setIsModelsOpen(false)}
          onStartAllModelDownloads={() => void startAllModelDownloads()}
          onStartModelDownload={(modelName) => void startModelDownload(modelName)}
        />
      )}
    </main>
  );
}
