import { FileAudio, FolderOpen, Play, Upload, X } from "lucide-react";
import type { FormEvent } from "react";

export const UPLOAD_UNSUPPORTED_MEDIA_MESSAGE =
  "Этот тип файла не поддерживается. Выберите аудио или видео файл.";

export const SUPPORTED_MEDIA_EXTENSIONS = [
  "mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "mov", "mkv", "avi", "webm"
] as const;

const SUPPORTED_MEDIA_EXTENSION_SET = new Set<string>(SUPPORTED_MEDIA_EXTENSIONS);

export const SUPPORTED_MEDIA_ACCEPT = [
  "audio/*",
  "video/*",
  ...Array.from(SUPPORTED_MEDIA_EXTENSIONS, (extension) => `.${extension}`)
].join(",");

export function isSupportedMediaFile(file: Pick<File, "name" | "type">): boolean {
  if (file.type.startsWith("audio/") || file.type.startsWith("video/")) return true;
  return SUPPORTED_MEDIA_EXTENSION_SET.has(file.name.split(".").pop()?.toLowerCase() ?? "");
}

export function filenameFromPath(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

interface UploadPanelProps {
  batchFilenames: string[];
  canSubmitJob: boolean;
  isSubmitting: boolean;
  isDragActive: boolean;
  isTauri: boolean;
  mediaFilename: string | null;
  outputDirectory: string | null;
  selectedModelIsReady: boolean;
  selectedModelStatusText: string;
  selectedModelTitle: string;
  title: string;
  uploadError: string | null;
  onChooseFiles: () => void;
  onChooseOutputDirectory: () => void;
  onClearSelection: () => void;
  onFilesSelected: (files: File[]) => void;
  onOpenSettings: () => void;
  onSubmitJob: (event: FormEvent) => void;
  onTitleChange: (value: string) => void;
}

export function UploadPanel({
  batchFilenames,
  canSubmitJob,
  isSubmitting,
  isDragActive,
  isTauri,
  mediaFilename,
  outputDirectory,
  selectedModelIsReady,
  selectedModelStatusText,
  selectedModelTitle,
  title,
  uploadError,
  onChooseFiles,
  onChooseOutputDirectory,
  onClearSelection,
  onFilesSelected,
  onOpenSettings,
  onSubmitJob,
  onTitleChange
}: UploadPanelProps) {
  const hasSelection = Boolean(mediaFilename) || batchFilenames.length > 0;
  const batchLabel = batchFilenames.length === 2 ? "2 файла" : `${batchFilenames.length} файлов`;
  const primaryFilename = mediaFilename ?? (batchFilenames.length ? `Пакет · ${batchLabel}` : null);

  return (
    <form className={`new-transcription-screen${hasSelection ? " has-file" : ""}`} onSubmit={onSubmitJob}>
      <header className="screen-header">
        <div>
          <p className="eyebrow">Mnema</p>
          <h1>Новая транскрипция</h1>
          <p>Добавьте аудио или видео</p>
        </div>
      </header>

      <div className={`drop-surface${isDragActive ? " is-drag-active" : ""}${uploadError ? " has-error" : ""}${hasSelection ? " has-file" : ""}`}>
        <span className="editorial-cut" aria-hidden="true" />
        {hasSelection ? <FileAudio className="drop-icon" size={34} /> : <Upload className="drop-icon" size={34} />}
        <strong>{isDragActive ? "Отпустите файлы здесь" : primaryFilename ?? "Перетащите записи сюда"}</strong>
        <small>{batchFilenames.length ? "Файлы переданы в пакетную сессию" : mediaFilename ? "Файл готов к обработке" : "Можно добавить один или несколько файлов"}</small>
        {isTauri ? (
          <button className="secondary-button file-button" type="button" onClick={onChooseFiles}>Выбрать файлы</button>
        ) : (
          <label className="secondary-button file-button">
            Выбрать файлы
            <input aria-label="Выбрать файл" type="file" multiple accept={SUPPORTED_MEDIA_ACCEPT} onChange={(event) => onFilesSelected(Array.from(event.target.files ?? []))} />
          </label>
        )}
      </div>

      {uploadError && <p className="inline-error" role="alert">{uploadError}</p>}

      {hasSelection && (
        <section className="file-setup">
          <button className="remove-file" aria-label="Убрать файл" type="button" onClick={onClearSelection}><X size={16} /> Убрать</button>
          {batchFilenames.length > 0 && <p className="batch-entry-copy">Пакет · {batchLabel}. Настройка очереди продолжится в пакетном экране.</p>}
          {mediaFilename && (
            <label className="title-field">
              <span>Название</span>
              <input value={title} onChange={(event) => onTitleChange(event.target.value)} />
            </label>
          )}
          <div className="destination-row">
            <FolderOpen size={18} />
            <span><small>Сохранить в</small><strong>{outputDirectory ?? "Папка не выбрана"}</strong></span>
            <button className="text-button" type="button" onClick={onChooseOutputDirectory}>{outputDirectory ? "Изменить" : "Выбрать папку"}</button>
          </div>
          {!outputDirectory && <button className="text-button open-settings-link" type="button" onClick={onOpenSettings}>Открыть настройки</button>}
          {!selectedModelIsReady && (
            <div className="model-problem" role="status">
              <strong>Модель распознавания не готова</strong>
              <span>{selectedModelTitle} · {selectedModelStatusText}</span>
              <button className="text-button" type="button" onClick={onOpenSettings}>Открыть настройки моделей</button>
            </div>
          )}
          <div className="setup-actions">
            <span className="model-caption">Модель: {selectedModelTitle}</span>
            <button className="primary-button" disabled={!canSubmitJob || !outputDirectory || batchFilenames.length > 0} type="submit">
              <Play size={17} /> {isSubmitting ? "Запускаю…" : "Начать транскрибацию"}
            </button>
          </div>
        </section>
      )}
    </form>
  );
}