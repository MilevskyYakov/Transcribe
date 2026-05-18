import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient, normalizeBaseUrl } from "./api";
import { loadWebDefaultModel, resolveAppEnvironment, saveDefaultModel } from "./appEnvironment";
import {
  canChooseModelAsDefault,
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
  titleFromFilename
} from "./appViewModel";
import { AppSidebar } from "./components/AppSidebar";
import { JobWorkspace } from "./components/JobWorkspace";
import { ModelsModal } from "./components/ModelsModal";
import { UploadPanel } from "./components/UploadPanel";
import type {
  AppEnvironment,
  Artifact,
  HealthPayload,
  Job,
  JobEvent,
  ModelsPayload,
  TranscriptSegment
} from "./types";

export {
  artifactDisplayName,
  canChooseModelAsDefault,
  canStartWithDefaultModel,
  compareArtifactsForDisplay,
  currentMessage,
  currentProgressLabel,
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
  titleFromFilename,
  type SpeakerTurn
} from "./appViewModel";

export function App() {
  const [apiBase, setApiBase] = useState(
    () => localStorage.getItem("transcribe-doc-api-base") ?? DEFAULT_API_BASE
  );
  const [appEnvironment, setAppEnvironment] = useState<AppEnvironment | null>(null);
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
  const [isModelsOpen, setIsModelsOpen] = useState(false);
  const [batchPaths, setBatchPaths] = useState("");
  const [watchFolder, setWatchFolder] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [models, setModels] = useState<ModelsPayload | null>(null);

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
  const canSubmitJob = Boolean(mediaFile) && !isSubmitting && selectedModelIsReady;
  const selectedJobRefreshKey = selectedJobDetailsRefreshKey(selectedJob);
  const selectedSpeakerTurns = useMemo(() => speakerTurns(segments), [segments]);
  const selectedDiarizationDiagnostic = diarizationDiagnostic(selectedJob);

  const refresh = useCallback(async () => {
    try {
      const nextHealth = await client.health();
      setHealth("ok");
      setHealthDetails(nextHealth);
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
      setNotice(error instanceof Error ? error.message : "Сервис недоступен");
    }
  }, [client]);

  useEffect(() => {
    let isActive = true;
    void resolveAppEnvironment(DEFAULT_API_BASE).then((environment) => {
      if (!isActive) return;
      setAppEnvironment(environment);
      if (environment.isTauri) {
        setApiBase(environment.apiBaseUrl);
        if (environment.defaultModelName) {
          setSelectedModelName(environment.defaultModelName);
        }
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
    if (!hasActiveJobs && !hasModelDownload) return;
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, hasModelDownload, refresh]);

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
      return;
    }
    let isActive = true;
    Promise.all([
      client.getTranscript(selectedJobId),
      client.listArtifacts(selectedJobId),
      client.listEvents(selectedJobId)
    ])
      .then(([transcript, nextArtifacts, nextEvents]) => {
        if (!isActive) return;
        setSegments(transcript.segments);
        setArtifacts(nextArtifacts);
        setEvents(nextEvents);
      })
      .catch((error) => {
        if (isActive) setNotice(error instanceof Error ? error.message : "Задача недоступна");
      });
    return () => {
      isActive = false;
    };
  }, [client, selectedJobId, selectedJobRefreshKey]);

  function handleMediaFileChange(file: File | null) {
    setMediaFile(file);
    setTranscriptionTitle(file ? titleFromFilename(file.name) : "");
  }

  async function submitJob(event: FormEvent) {
    event.preventDefault();
    if (!mediaFile) return;
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

  return (
    <main className="app-shell">
      <AppSidebar
        apiBase={apiBase}
        batchPaths={batchPaths}
        cacheDir={cacheDir}
        ffmpegAvailable={ffmpegAvailable}
        ffprobeAvailable={ffprobeAvailable}
        health={health}
        isManagedApp={isManagedApp}
        isSubmitting={isSubmitting}
        jobs={jobs}
        outputDir={outputDir}
        selectedJobId={selectedJobId}
        selectedModelTitle={selectedModelTitle}
        watchFolder={watchFolder}
        onApiBaseChange={setApiBase}
        onBatchPathsChange={setBatchPaths}
        onModelsOpen={() => setIsModelsOpen(true)}
        onRefresh={() => void refresh()}
        onSelectJob={setSelectedJobId}
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
          transcriptionTitle={transcriptionTitle}
          onMediaFileChange={handleMediaFileChange}
          onSpeakerHintChange={setSpeakerHint}
          onSubmitJob={(event) => void submitJob(event)}
          onTranscriptionTitleChange={setTranscriptionTitle}
        />
        <JobWorkspace
          artifacts={artifacts}
          client={client}
          events={events}
          isSelectedJobQuiet={isSelectedJobQuiet}
          notice={notice}
          now={now}
          selectedDiarizationDiagnostic={selectedDiarizationDiagnostic}
          selectedDisplayWarnings={selectedDisplayWarnings}
          selectedJob={selectedJob}
          selectedJobDisplayStatus={selectedJobDisplayStatus}
          selectedLastEventTime={selectedLastEventTime}
          selectedSpeakerTurns={selectedSpeakerTurns}
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
