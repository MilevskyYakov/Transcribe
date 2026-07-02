import { describe, expect, it } from "vitest";
import { isSupportedMediaFile, UPLOAD_UNSUPPORTED_MEDIA_MESSAGE } from "./components/UploadPanel";

describe("upload file validation", () => {
  it("accepts the backend-supported audio and video extensions even without a MIME type", () => {
    for (const name of ["meeting.mp3", "call.WAV", "voice.m4a", "clip.aac", "recording.flac", "audio.ogg"]) {
      expect(isSupportedMediaFile({ name, type: "" }), name).toBe(true);
    }

    for (const name of ["demo.mp4", "phone.MOV", "capture.mkv", "camera.avi", "screen.webm"]) {
      expect(isSupportedMediaFile({ name, type: "" }), name).toBe(true);
    }
  });

  it("accepts browser-provided audio/video MIME types", () => {
    expect(isSupportedMediaFile({ name: "blob", type: "audio/webm" })).toBe(true);
    expect(isSupportedMediaFile({ name: "recording", type: "video/quicktime" })).toBe(true);
  });

  it("rejects unsupported files and folder-like drops", () => {
    expect(isSupportedMediaFile({ name: "notes.txt", type: "text/plain" })).toBe(false);
    expect(isSupportedMediaFile({ name: "Photos", type: "" })).toBe(false);
    expect(UPLOAD_UNSUPPORTED_MEDIA_MESSAGE).toBe(
      "Этот тип файла не поддерживается. Выберите аудио или видео файл."
    );
  });
});
