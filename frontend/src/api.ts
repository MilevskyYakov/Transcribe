import type {
  Artifact,
  BatchSession,
  FinalMarkdownStatus,
  HealthPayload,
  Job,
  JobEvent,
  ModelsPayload,
  SpeakerReviewPayload,
  TempCleanupReport,
  TranscriptSegment,
  WordToken
} from "./types";

export interface TranscriptPayload {
  job: Job | null;
  segments: TranscriptSegment[];
  words: WordToken[];
}

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  async health(): Promise<HealthPayload> {
    return this.get("/health");
  }

  async listJobs(): Promise<Job[]> {
    const payload = await this.get<{ jobs: Job[] }>("/jobs");
    return payload.jobs;
  }

  async listBatchSessions(): Promise<BatchSession[]> {
    const payload = await this.get<{ batch_sessions: BatchSession[] }>("/batch-sessions");
    return payload.batch_sessions;
  }

  async createBatchSession(
    items: { inputPath?: string; sourceName: string }[],
    commonOutputDir?: string | null
  ): Promise<BatchSession> {
    const response = await fetch(`${this.baseUrl}/batch-sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items.map((item) => ({ input_path: item.inputPath, source_name: item.sourceName })),
        common_output_dir: commonOutputDir || undefined
      })
    });
    const payload = await this.parseResponse<{ batch_session: BatchSession }>(response);
    return payload.batch_session;
  }

  async updateBatchSessionOutput(sessionId: string, commonOutputDir: string): Promise<BatchSession> {
    const response = await fetch(
      `${this.baseUrl}/batch-sessions/${encodeURIComponent(sessionId)}/common-output`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ common_output_dir: commonOutputDir })
      }
    );
    const payload = await this.parseResponse<{ batch_session: BatchSession }>(response);
    return payload.batch_session;
  }

  async submitBatchSessionItem(
    sessionId: string,
    itemId: string,
    media: File | string,
    displayTitle: string,
    finalMarkdownDir: string,
    speakerHint?: string,
    asrBackend?: string,
    asrModelName?: string
  ): Promise<{ batch_session: BatchSession; job: Job }> {
    const url = `${this.baseUrl}/batch-sessions/${encodeURIComponent(sessionId)}/items/${encodeURIComponent(itemId)}/submit`;
    if (typeof media === "string") {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: media,
          display_title: displayTitle,
          final_markdown_dir: finalMarkdownDir,
          speaker_hint: speakerHint?.trim() || undefined,
          asr_backend: asrBackend,
          asr_model_name: asrModelName
        })
      });
      return this.parseResponse(response);
    }
    const formData = new FormData();
    formData.append("media", media);
    formData.append("display_title", displayTitle);
    formData.append("final_markdown_dir", finalMarkdownDir);
    if (speakerHint?.trim()) formData.append("speaker_hint", speakerHint.trim());
    if (asrBackend) formData.append("asr_backend", asrBackend);
    if (asrModelName) formData.append("asr_model_name", asrModelName);
    const response = await fetch(url, { method: "POST", body: formData });
    return this.parseResponse(response);
  }

  async getJob(jobId: string): Promise<Job> {
    const payload = await this.get<{ job: Job }>(`/jobs/${encodeURIComponent(jobId)}`);
    return payload.job;
  }

  async getTranscript(jobId: string): Promise<TranscriptPayload> {
    return this.get(`/jobs/${encodeURIComponent(jobId)}/transcript`);
  }

  async listArtifacts(jobId: string): Promise<Artifact[]> {
    const payload = await this.get<{ artifacts: Artifact[] }>(
      `/jobs/${encodeURIComponent(jobId)}/artifacts`
    );
    return payload.artifacts;
  }

  async listEvents(jobId: string): Promise<JobEvent[]> {
    const payload = await this.get<{ events: JobEvent[] }>(
      `/jobs/${encodeURIComponent(jobId)}/events`
    );
    return payload.events;
  }

  async finalMarkdownStatus(jobId: string): Promise<FinalMarkdownStatus> {
    return this.get(`/jobs/${encodeURIComponent(jobId)}/final-markdown`);
  }

  async speakerReview(jobId: string): Promise<SpeakerReviewPayload> {
    return this.get(`/jobs/${encodeURIComponent(jobId)}/speaker-review`);
  }

  async saveSpeakerReview(
    jobId: string,
    assignments: Record<string, string>,
    options: { skipped?: boolean; autosaveDir?: string | null } = {}
  ): Promise<{ speaker_review: SpeakerReviewPayload; final_markdown?: FinalMarkdownStatus }> {
    const response = await fetch(`${this.baseUrl}/jobs/${encodeURIComponent(jobId)}/speaker-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        assignments,
        skipped: options.skipped ?? false,
        autosave_dir: options.autosaveDir || undefined
      })
    });
    return this.parseResponse(response);
  }

  async saveFinalMarkdown(jobId: string, autosaveDir: string): Promise<FinalMarkdownStatus> {
    const response = await fetch(`${this.baseUrl}/jobs/${encodeURIComponent(jobId)}/final-markdown`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ autosave_dir: autosaveDir })
    });
    return this.parseResponse(response);
  }

  async listModels(): Promise<ModelsPayload> {
    return this.get("/models");
  }

  async downloadModel(modelName: string): Promise<{ status: string; message: string; model: string }> {
    const response = await fetch(`${this.baseUrl}/models/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_name: modelName })
    });
    return this.parseResponse(response);
  }

  async downloadAllModels(): Promise<{ status: string; message: string; started: string[]; skipped: string[] }> {
    const response = await fetch(`${this.baseUrl}/models/download-all`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    return this.parseResponse(response);
  }

  async cleanupTemporaryFiles(): Promise<TempCleanupReport> {
    const response = await fetch(`${this.baseUrl}/cleanup/temp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    return this.parseResponse(response);
  }

  async createJob(
    media: File | string,
    displayTitle?: string,
    speakerHint?: string,
    asrBackend?: string,
    asrModelName?: string,
    finalMarkdownDir?: string
  ): Promise<Job | null> {
    if (typeof media === "string") {
      const response = await fetch(`${this.baseUrl}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: media,
          display_title: displayTitle?.trim() || undefined,
          speaker_hint: speakerHint?.trim() || undefined,
          asr_backend: asrBackend,
          asr_model_name: asrModelName,
          final_markdown_dir: finalMarkdownDir
        })
      });
      return this.parseResponse<{ job: Job | null }>(response).then((payload) => payload.job);
    }
    const formData = new FormData();
    formData.append("media", media);
    if (displayTitle?.trim()) {
      formData.append("display_title", displayTitle.trim());
    }
    if (speakerHint?.trim()) {
      formData.append("speaker_hint", speakerHint.trim());
    }
    if (asrBackend) {
      formData.append("asr_backend", asrBackend);
    }
    if (asrModelName) {
      formData.append("asr_model_name", asrModelName);
    }
    if (finalMarkdownDir) {
      formData.append("final_markdown_dir", finalMarkdownDir);
    }
    const response = await fetch(`${this.baseUrl}/jobs`, {
      method: "POST",
      body: formData
    });
    return this.parseResponse<{ job: Job | null }>(response).then((payload) => payload.job);
  }

  async createBatch(
    inputPaths: string[],
    speakerHint?: string,
    asrBackend?: string,
    asrModelName?: string
  ): Promise<{ total: number; succeeded: number; failed: number }> {
    const response = await fetch(`${this.baseUrl}/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input_paths: inputPaths,
        speaker_hint: speakerHint?.trim() || undefined,
        asr_backend: asrBackend,
        asr_model_name: asrModelName
      })
    });
    return this.parseResponse(response);
  }

  async scanWatchFolder(inputDir: string): Promise<{ total: number; succeeded: number; failed: number }> {
    const response = await fetch(`${this.baseUrl}/watch-folder/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_dir: inputDir, stability_seconds: 0 })
    });
    return this.parseResponse(response);
  }

  artifactUrl(artifact: Artifact): string {
    return `${this.baseUrl}${artifact.download_url}`;
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`);
    return this.parseResponse<T>(response);
  }

  private async parseResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json() as Promise<T>;
  }
}

export function normalizeBaseUrl(value: string): string {
  return value.replace(/\/+$/, "");
}
