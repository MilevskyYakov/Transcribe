import { describe, expect, it } from "vitest";
import {
  canChooseModelAsDefault,
  canStartWithDefaultModel,
  currentMessage,
  currentProgressLabel,
  defaultModelActionLabel,
  diarizationDiagnostic,
  displayStatus,
  displayWarnings,
  eventDisplayMessage,
  eventDisplayStatus,
  eventMessageForTest,
  artifactDisplayName,
  compareArtifactsForDisplay,
  isRawRuntimeDetail,
  jobDisplayTitle,
  modelDownloadActionLabel,
  speakerTurns,
  titleFromFilename,
  selectedJobDetailsRefreshKey
} from "./App";
import type { Artifact, Job, ModelStatus } from "./types";

function model(status: ModelStatus["status"], name = status): ModelStatus {
  return { name, status };
}

describe("job status presentation", () => {
  it("keeps raw runtime errors out of the progress headline", () => {
    const job: Job = {
      job_id: "job-1",
      source_paths: [],
      status: "failed",
      detected_language: null,
      artifacts: {},
      metadata: {
        progress: 35,
        last_message: "[ONNXRuntimeError] CoreMLExecutionProvider raw failure"
      },
      warnings: ["[ONNXRuntimeError] CoreMLExecutionProvider raw failure"]
    };

    expect(currentMessage(job)).toBe("Обработка остановилась с ошибкой");
    expect(currentProgressLabel(job)).toBe("остановилось на 35%");
    expect(isRawRuntimeDetail(job.warnings[0])).toBe(true);
  });

  it("hides raw runtime event text outside diagnostics", () => {
    expect(
      eventMessageForTest({
        timestamp: "2026-05-12T09:08:43Z",
        stage: "failed",
        status: "error",
        message: "[ONNXRuntimeError] CoreMLExecutionProvider raw failure",
        progress: 35
      })
    ).toBe("Обработка остановилась с ошибкой");
  });

  it("changes details refresh key when the same selected job progresses", () => {
    const baseJob: Job = {
      job_id: "job-1",
      source_paths: [],
      status: "processing",
      detected_language: null,
      artifacts: {},
      metadata: {
        progress: 35,
        current_stage: "asr"
      },
      warnings: []
    };

    expect(
      selectedJobDetailsRefreshKey({
        ...baseJob,
        status: "completed_with_warnings",
        metadata: { progress: 100, current_stage: "done" }
      })
    ).not.toBe(selectedJobDetailsRefreshKey(baseJob));
  });
});

describe("job titles", () => {
  it("uses explicit titles, source filenames, then job ids", () => {
    const baseJob: Job = {
      job_id: "job-1",
      source_paths: ["/tmp/meeting-audio.wav"],
      status: "completed",
      detected_language: null,
      artifacts: {},
      metadata: {},
      warnings: []
    };

    expect(titleFromFilename("/tmp/client-call.mp3")).toBe("client-call");
    expect(jobDisplayTitle({ ...baseJob, metadata: { display_title: "Созвон" } })).toBe("Созвон");
    expect(jobDisplayTitle({ ...baseJob, metadata: { source_filename: "raw-talk.m4a" } })).toBe(
      "raw-talk"
    );
    expect(jobDisplayTitle({ ...baseJob, source_paths: [], metadata: {} })).toBe("job-1");
  });
});

describe("transcript presentation", () => {
  it("groups adjacent chunks by speaker role instead of showing each timed chunk first", () => {
    const turns = speakerTurns([
      {
        segment_id: "seg-001",
        start_seconds: 0,
        end_seconds: 20,
        text_raw: "первая часть",
        text_clean: "первая часть",
        speaker_label: "Менеджер"
      },
      {
        segment_id: "seg-002",
        start_seconds: 20,
        end_seconds: 60,
        text_raw: "продолжение",
        text_clean: "продолжение",
        speaker_label: "Менеджер"
      },
      {
        segment_id: "seg-003",
        start_seconds: 60,
        end_seconds: 80,
        text_raw: "ответ",
        text_clean: "ответ",
        speaker_label: "Клиент"
      }
    ]);

    expect(turns).toEqual([
      {
        id: "seg-001",
        speakerLabel: "Менеджер",
        start_seconds: 0,
        end_seconds: 60,
        texts: ["первая часть", "продолжение"],
        segments: [
          {
            segment_id: "seg-001",
            start_seconds: 0,
            end_seconds: 20,
            text_raw: "первая часть",
            text_clean: "первая часть",
            speaker_label: "Менеджер"
          },
          {
            segment_id: "seg-002",
            start_seconds: 20,
            end_seconds: 60,
            text_raw: "продолжение",
            text_clean: "продолжение",
            speaker_label: "Менеджер"
          }
        ]
      },
      {
        id: "seg-003",
        speakerLabel: "Клиент",
        start_seconds: 60,
        end_seconds: 80,
        texts: ["ответ"],
        segments: [
          {
            segment_id: "seg-003",
            start_seconds: 60,
            end_seconds: 80,
            text_raw: "ответ",
            text_clean: "ответ",
            speaker_label: "Клиент"
          }
        ]
      }
    ]);
  });

  it("keeps word diagnostics inside grouped speaker turns", () => {
    const turns = speakerTurns([
      {
        segment_id: "seg-001",
        start_seconds: 0,
        end_seconds: 10,
        text_raw: "crm",
        text_clean: "CRM.",
        speaker_label: "Менеджер",
        words: [
          {
            text: "crm",
            text_clean: "CRM",
            start_seconds: 0,
            end_seconds: 0.4,
            issues: [
              {
                code: "domain_term",
                severity: "info",
                message: "Known domain term normalized."
              }
            ]
          }
        ]
      }
    ]);

    expect(turns[0].segments[0].words?.[0].text_clean).toBe("CRM");
    expect(turns[0].segments[0].words?.[0].issues?.[0].code).toBe("domain_term");
  });

  it("shows diarization quality as diagnostics, not a task warning", () => {
    const job: Job = {
      job_id: "job-1",
      source_paths: [],
      status: "completed",
      detected_language: "ru",
      artifacts: {},
      metadata: {
        diarization_quality: {
          min_centroid_similarity_margin: 0.05,
          detected_cluster_count_max: 2,
          dominant_cluster_share: 0.5
        }
      },
      warnings: []
    };

    expect(diarizationDiagnostic(job)).toContain("margin 0.05");
  });

  it("presents old diarization-only warning jobs as completed in the app", () => {
    const job: Job = {
      job_id: "job-1",
      source_paths: [],
      status: "completed_with_warnings",
      detected_language: "ru",
      artifacts: {},
      metadata: {
        progress: 100,
        last_message: "Задача завершена с предупреждениями",
        diarization_quality: {
          min_centroid_similarity_margin: 0.05,
          detected_cluster_count_max: 2
        }
      },
      warnings: [
        "Diarization quality warning: low cluster separation (min centroid margin=0.05)."
      ]
    };

    expect(displayStatus(job)).toBe("completed");
    expect(displayWarnings(job)).toEqual([]);
    expect(currentMessage(job)).toBe("Задача успешно завершена");
    expect(
      eventDisplayStatus(
        {
          timestamp: "2026-05-13T08:32:52Z",
          stage: "done",
          status: "warning",
          message: "Задача завершена с предупреждениями",
          progress: 100
        },
        job
      )
    ).toBe("ok");
    expect(
      eventDisplayMessage(
        {
          timestamp: "2026-05-13T08:32:52Z",
          stage: "done",
          status: "warning",
          message: "Задача завершена с предупреждениями",
          progress: 100
        },
        job
      )
    ).toBe("Задача успешно завершена");
  });
});

describe("artifact presentation", () => {
  it("highlights the final speech text as the primary output", () => {
    const finalText: Artifact = {
      name: "final_speech_text_md",
      filename: "final_speech_text.md",
      size_bytes: 120,
      download_url: "/jobs/job-1/artifacts/final_speech_text_md"
    };
    const segments: Artifact = {
      name: "segments_json",
      filename: "segments.json",
      size_bytes: 80,
      download_url: "/jobs/job-1/artifacts/segments_json"
    };

    expect(artifactDisplayName(finalText)).toBe("Готовый текст");
    expect([segments, finalText].sort(compareArtifactsForDisplay)[0]).toBe(finalText);
  });
});

describe("default model rules", () => {
  it("allows selecting only ready models as default", () => {
    expect(canChooseModelAsDefault(model("ready", "gigaam-v3"))).toBe(true);
    expect(canChooseModelAsDefault(model("missing", "small"))).toBe(false);
    expect(canChooseModelAsDefault(model("downloading", "parakeet-v3"))).toBe(false);
  });

  it("labels unavailable default actions clearly", () => {
    expect(defaultModelActionLabel(model("ready", "gigaam-v3"), "gigaam-v3")).toBe("Выбрана");
    expect(defaultModelActionLabel(model("ready", "small"), "gigaam-v3")).toBe("По умолчанию");
    expect(defaultModelActionLabel(model("missing", "small"), "small")).toBe("Сначала скачать");
    expect(defaultModelActionLabel(model("downloading", "parakeet-v3"), "gigaam-v3")).toBe(
      "Скачивается"
    );
  });

  it("blocks start when the selected model is not ready", () => {
    expect(canStartWithDefaultModel(model("ready", "gigaam-v3"))).toBe(true);
    expect(canStartWithDefaultModel(model("missing", "small"))).toBe(false);
    expect(canStartWithDefaultModel(null)).toBe(false);
  });

  it("offers recovery wording for interrupted downloads", () => {
    expect(modelDownloadActionLabel(model("missing", "small"))).toBe("Скачать");
    expect(modelDownloadActionLabel(model("downloading", "parakeet-v3"))).toBe("Повторить");
    expect(modelDownloadActionLabel({ ...model("error", "parakeet-v3"), stale_download: true })).toBe(
      "Скачать заново"
    );
  });
});
