import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent } from "react";
import { ApiClient, normalizeBaseUrl } from "./api";
import {
  chooseAutosaveMarkdownDir,
  chooseMediaPaths,
  isRegularFilePath,
  loadBackendStatus,
  loadWebAutosaveMarkdownDir,
  loadWebDefaultModel,
  markBackendOffline,
  markBackendOnline,
  openSavedMarkdownPath,
  revealSavedMarkdownPath,
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
  statusLabel,
  titleValidationMessage,
  titleFromFilename
} from "./appViewModel";
import { AppSidebar, type AppView } from "./components/AppSidebar";
import { BatchSessionPanel } from "./components/BatchSessionPanel";
import { JobWorkspace } from "./components/JobWorkspace";
import { ModelsModal } from "./components/ModelsModal";
import { SettingsPanel } from "./components/SettingsPanel";
import {
  filenameFromPath,
  isSupportedMediaFile,
  UploadPanel,
  UPLOAD_UNSUPPORTED_MEDIA_MESSAGE
} from "./components/UploadPanel";
import { formatBytes } from "./format";
import type {
  AppEnvironment,
  Artifact,
  BatchSession,
  BatchSessionItem,
  BackendLifecycle,
  FinalMarkdownStatus,
  HealthPayload,
  Job,
  JobEvent,
  ModelsPayload,
  SpeakerReviewPayload,
  TranscriptSegment
} from "./types";

interface MediaSelection {
  file?: File;
  name: string;
  path?: string;
}

export function batchFilesMatch(items: BatchSessionItem[], files: File[]): boolean {
  const missingItems = items.filter((item) => !item.input_path && item.status === "configure");
  return missingItems.length === files.length
    && missingItems.every((item, index) => item.source_name === files[index]?.name);
}

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
  const [batchSessions, setBatchSessions] = useState<BatchSession[]>([]);
  const [currentView, setCurrentView] = useState<AppView>("new");
  const [previousView, setPreviousView] = useState<AppView>("new");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedBatchSessionId, setSelectedBatchSessionId] = useState<string | null>(null);
  const [selectedBatchItemId, setSelectedBatchItemId] = useState<string | null>(null);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [mediaSelection, setMediaSelection] = useState<MediaSelection | null>(null);
  const [batchSelections, setBatchSelections] = useState<MediaSelection[]>([]);
  const [jobOutputDirectory, setJobOutputDirectory] = useState<string | null>(null);
  const [isWorkspaceDragActive, setIsWorkspaceDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [transcriptionTitle, setTranscriptionTitle] = useState("");
  const [speakerHint, setSpeakerHint] = useState("");
  const [selectedModelName, setSelectedModelName] = useState(() => loadWebDefaultModel() ?? "large-v3");
  const [autosaveMarkdownDir, setAutosaveMarkdownDir] = useState(() => loadWebAutosaveMarkdownDir());
  const [finalMarkdownStatus, setFinalMarkdownStatus] = useState<FinalMarkdownStatus | null>(null);
  const [speakerReview, setSpeakerReview] = useState<SpeakerReviewPayload | null>(null);
  const [isSavingFinalMarkdown, setIsSavingFinalMarkdown] = useState(false);
  const [isModelsOpen, setIsModelsOpen] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const [updateState, setUpdateState] = useState<UpdateState>(initialUpdateState);
  const [pendingUpdate, setPendingUpdate] = useState<PendingUpdate | null>(null);
  const workspaceRef = useRef<HTMLElement | null>(null);

  const client = useMemo(() => new ApiClient(normalizeBaseUrl(apiBase)), [apiBase]);
  const selectedJob = jobs.find((job) => job.job_id === selectedJobId) ?? null;
  const selectedBatchSession = batchSessions.find((session) => session.session_id === selectedBatchSessionId) ?? null;
  const selectedBatchItem = selectedBatchSession?.items.find((item) => item.item_id === selectedBatchItemId) ?? null;
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
  const transcriptionTitleError = mediaSelection ? titleValidationMessage(transcriptionTitle) : null;
  const canSubmitJob = canSubmitTranscriptionJob({
    hasMedia: Boolean(mediaSelection),
    transcriptionTitle,
    isSubmitting,
    selectedModelIsReady
  });
  const selectedJobRefreshKey = selectedJobDetailsRefreshKey(selectedJob);
  const selectedSpeakerTurns = useMemo(() => speakerTurns(segments), [segments]);
  const selectedDiarizationDiagnostic = diarizationDiagnostic(selectedJob);
  const visibleHistoryJobs = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase("ru");
    const batchJobIds = new Set(
      batchSessions.flatMap((session) => session.items.flatMap((item) => item.attempt_job_ids))
    );
    return jobs.filter((job) => !batchJobIds.has(job.job_id) && (!query || jobDisplayTitle(job).toLocaleLowerCase("ru").includes(query)));
  }, [batchSessions, jobs, searchQuery]);
  const visibleHistoryBatches = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase("ru");
    return batchSessions.filter((session) => !query || session.items.some((item) => item.display_title.toLocaleLowerCase("ru").includes(query)));
  }, [batchSessions, searchQuery]);

  const refresh = useCallback(async () => {
    try {
      const nextHealth = await client.health();
      setHealth("ok");
      setHealthDetails(nextHealth);
      setBackendHealthFailures(0);
      const onlineLifecycle = await markBackendOnline(isManagedApp);
      if (onlineLifecycle) setBackendLifecycle(onlineLifecycle);
      const [nextJobs, nextModels, nextBatchSessions] = await Promise.all([
        client.listJobs(),
        client.listModels(),
        client.listBatchSessions()
      ]);
      setJobs(nextJobs);
      setModels(nextModels);
      setBatchSessions(nextBatchSessions);
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
        setJobOutputDirectory((current) => current ?? environment.autosaveMarkdownDir ?? null);
      }
    });
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (!isManagedApp) return;
    let unlisten: (() => void) | undefined;
    let isActive = true;
    void import("@tauri-apps/api/webview")
      .then(({ getCurrentWebview }) => getCurrentWebview().onDragDropEvent((event) => {
        if (!isActive) return;
        if (event.payload.type === "leave") {
          setIsWorkspaceDragActive(false);
          return;
        }
        const rect = workspaceRef.current?.getBoundingClientRect();
        const scale = window.devicePixelRatio || 1;
        const position = event.payload.position;
        const isOverWorkspace = Boolean(rect)
          && position.x / scale >= rect!.left
          && position.x / scale <= rect!.right
          && position.y / scale >= rect!.top
          && position.y / scale <= rect!.bottom;
        setIsWorkspaceDragActive(isOverWorkspace);
        if (event.payload.type === "drop" && isOverWorkspace) {
          void selectNativePaths(event.payload.paths);
        }
      }))
      .then((nextUnlisten) => {
        if (isActive) unlisten = nextUnlisten;
        else nextUnlisten();
      })
      .catch((error) => setNotice(error instanceof Error ? error.message : "Native drag-and-drop недоступен"));
    return () => {
      isActive = false;
      unlisten?.();
    };
  }, [autosaveMarkdownDir, isManagedApp]);

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
    const destination = selectedJob.metadata.final_markdown_dir ?? autosaveMarkdownDir;
    if (!destination) {
      setNotice("Выберите папку для сохранения транскрипций");
      return;
    }
    if (isSavingFinalMarkdown) return;
    void saveSelectedFinalMarkdown(destination);
  }, [
    autosaveMarkdownDir,
    finalMarkdownStatus?.status,
    isSavingFinalMarkdown,
    selectedJob?.job_id,
    selectedJob?.status,
    speakerReview?.status
  ]);

  async function applyMediaSelections(selections: MediaSelection[]) {
    setUploadError(null);
    setSelectedJobId(null);
    setJobOutputDirectory(autosaveMarkdownDir);
    if (selections.length === 1) {
      setCurrentView("new");
      setSelectedBatchSessionId(null);
      setSelectedBatchItemId(null);
      setMediaSelection(selections[0]);
      setBatchSelections([]);
      setTranscriptionTitle(titleFromFilename(selections[0].name));
      return;
    }
    setMediaSelection(null);
    setBatchSelections(selections);
    const session = await client.createBatchSession(
      selections.map((selection) => ({ inputPath: selection.path, sourceName: selection.name })),
      autosaveMarkdownDir
    );
    setBatchSessions((current) => [session, ...current.filter((item) => item.session_id !== session.session_id)]);
    openBatchSession(session);
  }

  function selectBrowserFiles(files: File[]) {
    if (!files.length) return;
    if (files.some((file) => !isSupportedMediaFile(file))) {
      setUploadError(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE);
      return;
    }
    void applyMediaSelections(files.map((file) => ({ file, name: file.name }))).catch((error) => {
      setUploadError(error instanceof Error ? error.message : "Не удалось создать пакет");
    });
  }

  async function selectNativePaths(paths: string[]) {
    setIsWorkspaceDragActive(false);
    if (!paths.length) return;
    const selections = paths.map((path) => ({ name: filenameFromPath(path), path }));
    const regularFiles = await Promise.all(paths.map((path) => isRegularFilePath(path, true)));
    if (
      regularFiles.some((isFile) => !isFile)
      || selections.some((item) => !isSupportedMediaFile({ name: item.name, type: "" }))
    ) {
      setUploadError(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE);
      return;
    }
    await applyMediaSelections(selections);
  }

  async function chooseTranscriptionFiles() {
    try {
      const paths = await chooseMediaPaths(isManagedApp);
      if (paths.length) await selectNativePaths(paths);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Не удалось выбрать файлы");
    }
  }

  function clearMediaSelection() {
    setMediaSelection(null);
    setBatchSelections([]);
    setTranscriptionTitle("");
    setUploadError(null);
    setJobOutputDirectory(autosaveMarkdownDir);
  }

  function prepareBatchItem(item: BatchSessionItem | null, session: BatchSession) {
    setSelectedBatchItemId(item?.item_id ?? null);
    setTranscriptionTitle(item?.display_title ?? "");
    setJobOutputDirectory(item?.output_dir ?? session.common_output_dir ?? null);
  }

  function openBatchSession(session: BatchSession) {
    const nextItem = session.items.find((item) => item.status === "configure")
      ?? session.items.find((item) => item.status === "failed")
      ?? null;
    setSelectedBatchSessionId(session.session_id);
    setSelectedJobId(null);
    setCurrentView("batch");
    prepareBatchItem(nextItem, session);
  }

  function selectBatchItem(item: BatchSessionItem) {
    if (!selectedBatchSession || !["configure", "failed"].includes(item.status)) return;
    const firstConfigureItem = selectedBatchSession.items.find((entry) => entry.status === "configure");
    if (item.status === "configure" && firstConfigureItem?.item_id !== item.item_id) return;
    prepareBatchItem(item, selectedBatchSession);
  }

  function reattachBatchFiles(files: File[]) {
    if (!selectedBatchSession || files.some((file) => !isSupportedMediaFile(file))) {
      setNotice(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE);
      return;
    }
    const missingItems = selectedBatchSession.items.filter(
      (item) => !item.input_path && item.status === "configure"
    );
    if (!batchFilesMatch(selectedBatchSession.items, files)) {
      setNotice("Выберите оставшиеся файлы пакета в исходном порядке.");
      return;
    }
    setBatchSelections((current) => {
      const next = [...current];
      missingItems.forEach((item, index) => {
        next[item.position - 1] = { file: files[index], name: files[index].name };
      });
      return next;
    });
    setNotice("Файлы пакета подключены повторно.");
  }

  function storeBatchSession(session: BatchSession) {
    setBatchSessions((current) => [
      session,
      ...current.filter((item) => item.session_id !== session.session_id)
    ]);
  }

  function handleWorkspaceDrag(event: DragEvent<HTMLElement>) {
    if (isManagedApp) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setIsWorkspaceDragActive(true);
  }

  function handleWorkspaceDragLeave(event: DragEvent<HTMLElement>) {
    if (isManagedApp) return;
    event.preventDefault();
    const nextTarget = event.relatedTarget instanceof Node ? event.relatedTarget : null;
    if (!nextTarget || !event.currentTarget.contains(nextTarget)) setIsWorkspaceDragActive(false);
  }

  function handleWorkspaceDrop(event: DragEvent<HTMLElement>) {
    if (isManagedApp) return;
    event.preventDefault();
    setIsWorkspaceDragActive(false);
    selectBrowserFiles(Array.from(event.dataTransfer.files));
  }

  async function submitJob(event: FormEvent) {
    event.preventDefault();
    if (!mediaSelection) return;
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
        mediaSelection.file ?? mediaSelection.path ?? "",
        transcriptionTitle,
        speakerHint,
        selectedModel?.backend,
        selectedModel?.name ?? selectedModelName,
        jobOutputDirectory ?? undefined
      );
      await refresh();
      setSelectedJobId(job?.job_id ?? null);
      setCurrentView("job");
      setMediaSelection(null);
      setBatchSelections([]);
      setTranscriptionTitle("");
      setNotice("Задача поставлена в очередь");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось запустить задачу");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitBatchItem(event: FormEvent) {
    event.preventDefault();
    if (!selectedBatchSession || !selectedBatchItem || !jobOutputDirectory) return;
    const titleError = titleValidationMessage(transcriptionTitle);
    if (titleError) {
      setNotice(titleError);
      return;
    }
    if (!selectedModelIsReady) {
      setNotice("Выберите готовую модель распознавания или скачайте текущую модель.");
      setIsModelsOpen(true);
      return;
    }
    const browserFile = batchSelections[selectedBatchItem.position - 1]?.file;
    const media = browserFile ?? selectedBatchItem.input_path;
    if (!media) {
      setNotice("Файл недоступен после перезапуска browser-режима. Подключите файлы повторно.");
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await client.submitBatchSessionItem(
        selectedBatchSession.session_id,
        selectedBatchItem.item_id,
        media,
        transcriptionTitle,
        jobOutputDirectory,
        speakerHint,
        selectedModel?.backend,
        selectedModel?.name ?? selectedModelName
      );
      storeBatchSession(result.batch_session);
      const nextItem = result.batch_session.items.find((item) => item.status === "configure") ?? null;
      prepareBatchItem(nextItem, result.batch_session);
      await refresh();
      setNotice(nextItem ? "Файл запущен. Настройте следующий." : "Все файлы настроены. Обработка продолжается в фоне.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось запустить файл");
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
      setJobOutputDirectory((current) => current ?? saved);
      setAppEnvironment((current) => (current ? { ...current, autosaveMarkdownDir: saved } : current));
      setNotice(saved ? `Папка сохранения: ${saved}` : null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось выбрать папку сохранения");
    }
  }

  async function chooseJobOutputDirectory() {
    try {
      let selected = await chooseAutosaveMarkdownDir(isManagedApp);
      if (!selected && !isManagedApp) {
        selected = window.prompt("Папка для этой транскрипции", jobOutputDirectory ?? autosaveMarkdownDir ?? "");
      }
      if (selected) setJobOutputDirectory(selected);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось выбрать папку сохранения");
    }
  }

  async function chooseBatchCommonOutputDirectory() {
    if (!selectedBatchSession) return;
    try {
      let selected = await chooseAutosaveMarkdownDir(isManagedApp);
      if (!selected && !isManagedApp) {
        selected = window.prompt(
          "Общая папка пакета",
          selectedBatchSession.common_output_dir ?? autosaveMarkdownDir ?? ""
        );
      }
      if (!selected) return;
      const session = await client.updateBatchSessionOutput(selectedBatchSession.session_id, selected);
      storeBatchSession(session);
      if (!selectedBatchItem?.output_dir_override && !selectedBatchItem?.job_id) {
        setJobOutputDirectory(selected);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось выбрать общую папку");
    }
  }

  async function chooseSelectedJobOutputDirectory() {
    try {
      let selected = await chooseAutosaveMarkdownDir(isManagedApp);
      if (!selected && !isManagedApp) {
        selected = window.prompt(
          "Папка для этой транскрипции",
          selectedJob?.metadata.final_markdown_dir ?? autosaveMarkdownDir ?? ""
        );
      }
      if (selected) await saveSelectedFinalMarkdown(selected);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось выбрать папку сохранения");
    }
  }

  async function saveSelectedFinalMarkdown(
    dir = selectedJob?.metadata.final_markdown_dir ?? autosaveMarkdownDir
  ) {
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
    const destination = selectedJob.metadata.final_markdown_dir ?? autosaveMarkdownDir;
    if (!destination) {
      setNotice("Выберите папку для сохранения транскрипций");
      return;
    }
    setIsSavingFinalMarkdown(true);
    try {
      const result = await client.saveSpeakerReview(selectedJob.job_id, assignments, {
        skipped,
        autosaveDir: destination
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

  async function showFinalMarkdownInFinder() {
    const path = finalMarkdownStatus?.path ?? selectedJob?.metadata.saved_markdown_path ?? null;
    if (!path) return;
    try {
      await revealSavedMarkdownPath(path, isManagedApp);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Не удалось показать файл в Finder");
    }
  }

  function openNewTranscription() {
    setCurrentView("new");
    setSelectedJobId(null);
    setSelectedBatchSessionId(null);
    setSelectedBatchItemId(null);
    setMediaSelection(null);
    setBatchSelections([]);
    setJobOutputDirectory(autosaveMarkdownDir);
    setTranscriptionTitle("");
    setNotice(null);
  }

  function openSettings() {
    if (currentView !== "settings") setPreviousView(currentView);
    setCurrentView("settings");
  }

  function selectJob(jobId: string) {
    setSelectedJobId(jobId);
    setCurrentView("job");
  }

  function selectBatchSession(sessionId: string) {
    const session = batchSessions.find((item) => item.session_id === sessionId);
    if (session) openBatchSession(session);
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
        batchSessions={batchSessions}
        currentView={currentView}
        jobs={jobs}
        searchQuery={searchQuery}
        selectedJobId={selectedJobId}
        selectedBatchSessionId={selectedBatchSessionId}
        onNewTranscription={openNewTranscription}
        onOpenHistory={() => setCurrentView("history")}
        onOpenSettings={openSettings}
        onSearchQueryChange={setSearchQuery}
        onSelectBatchSession={selectBatchSession}
        onSelectJob={selectJob}
      />

      <section
        className={`workspace${isWorkspaceDragActive ? " is-drag-active" : ""}`}
        ref={workspaceRef}
        onDragEnter={handleWorkspaceDrag}
        onDragOver={handleWorkspaceDrag}
        onDragLeave={handleWorkspaceDragLeave}
        onDrop={handleWorkspaceDrop}
      >
        {currentView !== "settings" && health === "down" && backendLifecycle?.state === "error" ? (
          <section className="backend-problem-screen">
            <p className="eyebrow">Ошибка запуска</p>
            <h1>Mnema не удалось запустить обработку</h1>
            <p>{backendLifecycle.human_message || "Локальный сервис недоступен."}</p>
            <div>
              <button className="primary-button" type="button" onClick={() => void retryBackendStart()}>Повторить запуск</button>
              <button className="text-button" type="button" onClick={openSettings}>Открыть диагностику</button>
            </div>
          </section>
        ) : currentView === "new" ? (
          <UploadPanel
            batchFilenames={batchSelections.map((item) => item.name)}
            canSubmitJob={canSubmitJob}
            isSubmitting={isSubmitting}
            isDragActive={isWorkspaceDragActive}
            isTauri={isManagedApp}
            mediaFilename={mediaSelection?.name ?? null}
            outputDirectory={jobOutputDirectory}
            selectedModelIsReady={selectedModelIsReady}
            selectedModelStatusText={selectedModelStatusText}
            selectedModelTitle={selectedModelTitle}
            title={transcriptionTitle}
            uploadError={uploadError}
            onChooseFiles={() => void chooseTranscriptionFiles()}
            onChooseOutputDirectory={() => void chooseJobOutputDirectory()}
            onClearSelection={clearMediaSelection}
            onFilesSelected={selectBrowserFiles}
            onOpenSettings={openSettings}
            onSubmitJob={(event) => void submitJob(event)}
            onTitleChange={setTranscriptionTitle}
          />
        ) : currentView === "batch" && selectedBatchSession ? (
          <BatchSessionPanel
            canSubmit={Boolean(selectedBatchItem && (selectedBatchItem.input_path || batchSelections[selectedBatchItem.position - 1]?.file) && !titleValidationMessage(transcriptionTitle) && selectedModelIsReady && !isSubmitting)}
            currentItem={selectedBatchItem}
            isSubmitting={isSubmitting}
            needsFileReattach={Boolean(selectedBatchItem && !selectedBatchItem.input_path && !batchSelections[selectedBatchItem.position - 1]?.file)}
            outputDirectory={jobOutputDirectory}
            session={selectedBatchSession}
            title={transcriptionTitle}
            onChooseCommonOutput={() => void chooseBatchCommonOutputDirectory()}
            onChooseItemOutput={() => void chooseJobOutputDirectory()}
            onFilesReattached={reattachBatchFiles}
            onOpenJob={selectJob}
            onSelectItem={selectBatchItem}
            onSubmit={(event) => void submitBatchItem(event)}
            onTitleChange={setTranscriptionTitle}
          />
        ) : currentView === "history" ? (
          <section className="history-screen">
            <header className="screen-header">
              <div><p className="eyebrow">Архив</p><h1>История</h1><p>Найдите и откройте прежнюю запись.</p></div>
            </header>
            <label className="history-search"><span>Поиск по записям</span><input autoFocus value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /></label>
            <div className="history-table">
              {visibleHistoryBatches.map((session) => (
                <details className="history-batch" key={session.session_id}>
                  <summary>
                    <span><strong>Пакет · {session.totals.total} файлов</strong><small>Готово {session.totals.ready} · Обрабатывается {session.totals.processing} · Ошибок {session.totals.failed}</small></span>
                  </summary>
                  <div>
                    <button type="button" onClick={() => selectBatchSession(session.session_id)}>
                      <span><strong>Открыть пакет</strong><small>Очередь и настройка файлов</small></span>
                    </button>
                    {session.items.map((item) => (
                      <button disabled={!item.job_id} key={item.item_id} type="button" onClick={() => item.job_id && selectJob(item.job_id)}>
                        <span><strong>{item.display_title}</strong><small>{item.output_dir ?? "Папка не выбрана"}</small></span>
                        <span className={`status-label ${item.status}`}>{item.status === "configure" ? "Настроить" : item.status === "processing" ? "Обрабатывается" : item.status === "ready" ? "Готово" : "Ошибка"}</span>
                      </button>
                    ))}
                  </div>
                </details>
              ))}
              {visibleHistoryJobs.map((job) => (
                <button type="button" key={job.job_id} onClick={() => selectJob(job.job_id)}>
                  <span><strong>{jobDisplayTitle(job)}</strong><small>{String(job.metadata.saved_markdown_dir ?? job.source_paths[0] ?? "Локальная задача")}</small></span>
                  <span className={`status-label ${displayStatus(job)}`}>{statusLabel(displayStatus(job))}</span>
                </button>
              ))}
              {!visibleHistoryJobs.length && !visibleHistoryBatches.length && <p className="empty-copy">Ничего не найдено</p>}
            </div>
          </section>
        ) : currentView === "settings" ? (
          <SettingsPanel
            apiBase={apiBase}
            autosaveMarkdownDir={autosaveMarkdownDir}
            backendLifecycle={backendLifecycle}
            cacheDir={cacheDir}
            ffmpegAvailable={ffmpegAvailable}
            ffprobeAvailable={ffprobeAvailable}
            health={health}
            isManagedApp={isManagedApp}
            isSubmitting={isSubmitting}
            outputDir={outputDir}
            selectedModelTitle={selectedModelTitle}
            updateState={updateState}
            onApiBaseChange={setApiBase}
            onChooseFolder={() => void chooseFinalMarkdownFolder()}
            onCleanupTemp={() => void cleanupTemporaryFiles()}
            onDone={() => setCurrentView(previousView === "settings" ? "new" : previousView)}
            onModelsOpen={() => setIsModelsOpen(true)}
            onRefresh={() => void refresh()}
            onRetryBackendStart={() => void retryBackendStart()}
            onUpdateAction={() => void handleUpdateAction()}
          />
        ) : selectedJob && selectedJobDisplayStatus ? (
          <JobWorkspace
            artifacts={artifacts}
            autosaveMarkdownDir={selectedJob.metadata.final_markdown_dir ?? autosaveMarkdownDir}
            client={client}
            events={events}
            finalMarkdownStatus={finalMarkdownStatus}
            isSavingFinalMarkdown={isSavingFinalMarkdown}
            notice={notice}
            selectedDisplayWarnings={selectedDisplayWarnings}
            selectedJob={selectedJob}
            selectedJobDisplayStatus={selectedJobDisplayStatus}
            selectedSpeakerTurns={selectedSpeakerTurns}
            speakerReview={speakerReview}
            onChooseFinalMarkdownFolder={() => void chooseSelectedJobOutputDirectory()}
            onNewTranscription={openNewTranscription}
            onOpenFinalMarkdown={() => void openFinalMarkdown()}
            onSaveFinalMarkdownAgain={() => void saveSelectedFinalMarkdown()}
            onSaveSpeakerAssignments={(assignments) => void saveSpeakerAssignments(assignments, false)}
            onShowInFinder={() => void showFinalMarkdownInFinder()}
            onSkipSpeakerAssignments={(assignments) => void saveSpeakerAssignments(assignments, true)}
          />
        ) : (
          <p className="empty-copy">Выберите задачу в истории.</p>
        )}
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
