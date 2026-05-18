import { Play, Upload } from "lucide-react";
import type { FormEvent } from "react";

interface UploadPanelProps {
  canSubmitJob: boolean;
  isSubmitting: boolean;
  mediaFile: File | null;
  selectedModelIsReady: boolean;
  selectedModelStatusText: string;
  selectedModelTitle: string;
  speakerHint: string;
  transcriptionTitle: string;
  onMediaFileChange: (file: File | null) => void;
  onSpeakerHintChange: (value: string) => void;
  onSubmitJob: (event: FormEvent) => void;
  onTranscriptionTitleChange: (value: string) => void;
}

export function UploadPanel({
  canSubmitJob,
  isSubmitting,
  mediaFile,
  selectedModelIsReady,
  selectedModelStatusText,
  selectedModelTitle,
  speakerHint,
  transcriptionTitle,
  onMediaFileChange,
  onSpeakerHintChange,
  onSubmitJob,
  onTranscriptionTitleChange
}: UploadPanelProps) {
  return (
    <form className="upload-hero" onSubmit={onSubmitJob}>
      <div>
        <p className="eyebrow">Новая запись</p>
        <h2>Загрузить запись</h2>
        <p>Выберите аудио или видео, добавьте участников при необходимости и запустите транскрибацию.</p>
      </div>
      <label className="hero-file-picker">
        <Upload size={28} />
        <span>{mediaFile?.name ?? "Выбрать файл"}</span>
        <input type="file" onChange={(event) => onMediaFileChange(event.target.files?.[0] ?? null)} />
      </label>
      <label className="speaker-input">
        <span>Название транскрибации</span>
        <input
          aria-label="Название транскрибации"
          type="text"
          placeholder="Например: Созвон с клиентом"
          value={transcriptionTitle}
          onChange={(event) => onTranscriptionTitleChange(event.target.value)}
        />
      </label>
      <label className="speaker-input">
        <span>Участники</span>
        <input
          aria-label="Кто был на встрече"
          type="text"
          placeholder="Например: Яков и Никита"
          value={speakerHint}
          onChange={(event) => onSpeakerHintChange(event.target.value)}
        />
      </label>
      <div className="upload-actions">
        <span>
          Модель: {selectedModelTitle}
          {!selectedModelIsReady && ` · ${selectedModelStatusText}`}
        </span>
        <button className="run-button" disabled={!canSubmitJob} type="submit">
          <Play size={17} />
          <span>{isSubmitting ? "Запуск" : "Запустить"}</span>
        </button>
      </div>
    </form>
  );
}
