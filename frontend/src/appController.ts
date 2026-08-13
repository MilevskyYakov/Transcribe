import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ApiClient } from "./api";
import { markBackendOffline, markBackendOnline } from "./appEnvironment";
import { deliverTerminalNotifications } from "./notifications";
import type {
  Artifact,
  BatchSession,
  BackendLifecycle,
  FinalMarkdownStatus,
  HealthPayload,
  Job,
  JobEvent,
  ModelsPayload,
  SpeakerReviewPayload,
  TranscriptSegment
} from "./types";

export interface MediaSelection {
  file?: File;
  name: string;
  path?: string;
}

export function createLatestRequest() {
  let generation = 0;
  return async function run<T>(
    load: () => Promise<T>,
    apply: (value: T) => void,
    fail?: (error: unknown) => void
  ): Promise<boolean> {
    const current = ++generation;
    try {
      const value = await load();
      if (current !== generation) return false;
      apply(value);
      return true;
    } catch (error) {
      if (current !== generation) return false;
      fail?.(error);
      return false;
    }
  };
}

export function useAppSnapshot(
  client: ApiClient,
  isManagedApp: boolean,
  backendLifecycleState: string | undefined,
  setBackendLifecycle: (value: BackendLifecycle) => void,
  setSelectedJobId: (update: (current: string | null) => string | null) => void,
  setNotice: (value: string | null) => void
) {
  const [health, setHealth] = useState<"unknown" | "ok" | "down">("unknown");
  const [healthDetails, setHealthDetails] = useState<HealthPayload | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [batchSessions, setBatchSessions] = useState<BatchSession[]>([]);
  const [models, setModels] = useState<ModelsPayload | null>(null);
  const latestRequest = useMemo(createLatestRequest, [client]);

  const refresh = useCallback(async () => {
    await latestRequest(
      async () => {
        const nextHealth = await client.health();
        const [nextJobs, nextModels, nextBatchSessions] = await Promise.all([
          client.listJobs(),
          client.listModels(),
          client.listBatchSessions()
        ]);
        return { nextHealth, nextJobs, nextModels, nextBatchSessions };
      },
      ({ nextHealth, nextJobs, nextModels, nextBatchSessions }) => {
        setHealth("ok");
        setHealthDetails(nextHealth);
        setJobs(nextJobs);
        setModels(nextModels);
        setBatchSessions(nextBatchSessions);
        setSelectedJobId((current) =>
          current && nextJobs.some((job) => job.job_id === current) ? current : null
        );
        setNotice(null);
        void markBackendOnline(isManagedApp).then((lifecycle) => {
          if (lifecycle) setBackendLifecycle(lifecycle);
        });
        void deliverTerminalNotifications(nextJobs, nextBatchSessions, isManagedApp);
      },
      (error) => {
        const message = error instanceof Error ? error.message : "Сервис недоступен";
        setHealth("down");
        setHealthDetails(null);
        setNotice(message);
        void markBackendOffline(isManagedApp, message).then((lifecycle) => {
          if (lifecycle) setBackendLifecycle(lifecycle);
        });
      }
    );
  }, [client, isManagedApp, latestRequest, setBackendLifecycle, setNotice, setSelectedJobId]);

  const hasActiveJobs = jobs.some((job) => job.status === "queued" || job.status === "processing");
  const hasModelDownload = models?.models.some((model) => model.status === "downloading") ?? false;
  const isRecoveringBackend = isManagedApp
    && ["starting", "checking", "offline", "restarting"].includes(backendLifecycleState ?? "");

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!hasActiveJobs && !hasModelDownload && !isRecoveringBackend) return;
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [hasActiveJobs, hasModelDownload, isRecoveringBackend, refresh]);

  return {
    batchSessions,
    health,
    healthDetails,
    jobs,
    models,
    refresh,
    setBatchSessions
  };
}

export function useSelectedJobDetails(
  client: ApiClient,
  selectedJobId: string | null,
  refreshKey: string,
  setNotice: (value: string | null) => void
) {
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [finalMarkdownStatus, setFinalMarkdownStatus] = useState<FinalMarkdownStatus | null>(null);
  const [speakerReview, setSpeakerReview] = useState<SpeakerReviewPayload | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    const current = ++generation.current;
    if (!selectedJobId) {
      setSegments([]);
      setArtifacts([]);
      setEvents([]);
      setFinalMarkdownStatus(null);
      setSpeakerReview(null);
      return;
    }
    Promise.all([
      client.getTranscript(selectedJobId),
      client.listArtifacts(selectedJobId),
      client.listEvents(selectedJobId),
      client.finalMarkdownStatus(selectedJobId),
      client.speakerReview(selectedJobId)
    ])
      .then(([transcript, nextArtifacts, nextEvents, nextFinalMarkdownStatus, nextSpeakerReview]) => {
        if (current !== generation.current) return;
        setSegments(transcript.segments);
        setArtifacts(nextArtifacts);
        setEvents(nextEvents);
        setFinalMarkdownStatus(nextFinalMarkdownStatus);
        setSpeakerReview(nextSpeakerReview);
      })
      .catch((error) => {
        if (current === generation.current) {
          setNotice(error instanceof Error ? error.message : "Задача недоступна");
        }
      });
  }, [client, refreshKey, selectedJobId, setNotice]);

  return {
    artifacts,
    events,
    finalMarkdownStatus,
    segments,
    setFinalMarkdownStatus,
    setSegments,
    setSpeakerReview,
    speakerReview
  };
}

export function useTranscriptionDraft() {
  const [mediaSelection, setMediaSelection] = useState<MediaSelection | null>(null);
  const [batchSelections, setBatchSelections] = useState<MediaSelection[]>([]);
  const [jobOutputDirectory, setJobOutputDirectory] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [transcriptionTitle, setTranscriptionTitle] = useState("");

  return {
    batchSelections,
    jobOutputDirectory,
    mediaSelection,
    setBatchSelections,
    setJobOutputDirectory,
    setMediaSelection,
    setTranscriptionTitle,
    setUploadError,
    transcriptionTitle,
    uploadError
  };
}
