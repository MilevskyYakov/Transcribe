import { FolderOpen, Play, RotateCcw } from "lucide-react";
import type { FormEvent } from "react";
import type { BatchItemStatus, BatchSession, BatchSessionItem } from "../types";
import { SUPPORTED_MEDIA_ACCEPT } from "./UploadPanel";

export function batchItemStatusLabel(status: BatchItemStatus): string {
  return {
    configure: "Настроить",
    processing: "Обрабатывается",
    ready: "Готово",
    failed: "Ошибка"
  }[status];
}

interface BatchSessionPanelProps {
  session: BatchSession;
  currentItem: BatchSessionItem | null;
  title: string;
  outputDirectory: string | null;
  needsFileReattach: boolean;
  canSubmit: boolean;
  isSubmitting: boolean;
  onTitleChange: (value: string) => void;
  onChooseCommonOutput: () => void;
  onChooseItemOutput: () => void;
  onFilesReattached: (files: File[]) => void;
  onSelectItem: (item: BatchSessionItem) => void;
  onOpenJob: (jobId: string) => void;
  onSubmit: (event: FormEvent) => void;
}

export function BatchSessionPanel({
  session,
  currentItem,
  title,
  outputDirectory,
  needsFileReattach,
  canSubmit,
  isSubmitting,
  onTitleChange,
  onChooseCommonOutput,
  onChooseItemOutput,
  onFilesReattached,
  onSelectItem,
  onOpenJob,
  onSubmit
}: BatchSessionPanelProps) {
  const isFinished = session.totals.configure === 0 && session.totals.processing === 0;
  const firstConfigureItemId = session.items.find((item) => item.status === "configure")?.item_id;

  return (
    <section className="batch-screen">
      <header className="screen-header">
        <div>
          <p className="eyebrow">Mnema</p>
          <h1>Пакет · {currentItem?.position ?? session.totals.total} из {session.totals.total}</h1>
          <p>{isFinished ? `Готово ${session.totals.ready}, ошибок ${session.totals.failed}` : "Настройте файл и сразу запускайте обработку"}</p>
        </div>
      </header>

      <div className="batch-layout">
        <form className="batch-setup" onSubmit={onSubmit}>
          <div className="destination-row batch-common-folder">
            <FolderOpen size={18} />
            <span><small>Общая папка</small><strong>{session.common_output_dir ?? "Папка не выбрана"}</strong></span>
            <button className="text-button" type="button" onClick={onChooseCommonOutput}>{session.common_output_dir ? "Изменить" : "Выбрать"}</button>
          </div>

          {currentItem ? (
            <>
              <div className="batch-current-file">
                <small>Текущий файл</small>
                <strong>{currentItem.source_name}</strong>
              </div>
              <label className="title-field">
                <span>Название</span>
                <input autoFocus value={title} onChange={(event) => onTitleChange(event.target.value)} />
              </label>
              <div className="destination-row">
                <FolderOpen size={18} />
                <span><small>Сохранить в</small><strong>{outputDirectory ?? "Папка не выбрана"}</strong></span>
                <button className="text-button" type="button" onClick={onChooseItemOutput}>Иначе…</button>
              </div>
              {needsFileReattach && (
                <label className="secondary-button batch-reattach">
                  Подключить оставшиеся файлы
                  <input
                    type="file"
                    multiple
                    accept={SUPPORTED_MEDIA_ACCEPT}
                    onChange={(event) => onFilesReattached(Array.from(event.target.files ?? []))}
                  />
                </label>
              )}
              <div className="setup-actions">
                <span className="model-caption">{currentItem.status === "failed" ? "Повторится только этот файл" : "После запуска откроется следующий файл"}</span>
                <button className="primary-button" disabled={!canSubmit || !outputDirectory} type="submit">
                  {currentItem.status === "failed" ? <RotateCcw size={17} /> : <Play size={17} />}
                  {isSubmitting ? "Запускаю…" : currentItem.status === "failed" ? "Повторить" : "Начать транскрибацию"}
                </button>
              </div>
            </>
          ) : (
            <p className="batch-finished-copy">Все файлы настроены. Обработка продолжится в фоне.</p>
          )}
        </form>

        <aside className="batch-queue" aria-label="Очередь пакета">
          <h2>Очередь</h2>
          {session.items.map((item) => (
            <button
              className={item.item_id === currentItem?.item_id ? "batch-item active" : "batch-item"}
              disabled={item.status === "configure" && item.item_id !== firstConfigureItemId}
              key={item.item_id}
              type="button"
              onClick={() => item.job_id && item.status !== "failed" ? onOpenJob(item.job_id) : onSelectItem(item)}
            >
              <span><small>{String(item.position).padStart(2, "0")}</small><strong>{item.display_title}</strong></span>
              <em className={`status-label ${item.status}`}>{batchItemStatusLabel(item.status)}</em>
            </button>
          ))}
        </aside>
      </div>
    </section>
  );
}
