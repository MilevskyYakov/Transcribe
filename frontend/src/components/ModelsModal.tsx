import { X } from "lucide-react";
import type { ModelsPayload } from "../types";
import {
  canChooseModelAsDefault,
  defaultModelActionLabel,
  modelDetail,
  modelDownloadActionLabel,
  modelLabel
} from "../appViewModel";

interface ModelsModalProps {
  models: ModelsPayload | null;
  selectedModelName: string;
  selectedModelTitle: string;
  onChooseDefaultModel: (modelName: string) => void;
  onClose: () => void;
  onStartAllModelDownloads: () => void;
  onStartModelDownload: (modelName: string) => void;
}

export function ModelsModal({
  models,
  selectedModelName,
  selectedModelTitle,
  onChooseDefaultModel,
  onClose,
  onStartAllModelDownloads,
  onStartModelDownload
}: ModelsModalProps) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-label="Модели распознавания"
        aria-modal="true"
        className="models-modal"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div>
            <p className="eyebrow">Настройка</p>
            <h2>Модели распознавания</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <div className="modal-toolbar">
          <span>По умолчанию: {selectedModelTitle}</span>
          <button className="secondary-action" type="button" onClick={onStartAllModelDownloads}>
            Скачать все модели
          </button>
        </div>
        <div className="model-list modal-list">
          {(models?.models ?? []).map((model) => (
            <article className={`model-row ${model.status}`} key={model.name}>
              <div>
                <strong>{model.label ?? model.name}</strong>
                <small>{modelDetail(model) || model.name}</small>
              </div>
              <span>{modelLabel(model)}</span>
              {model.status === "downloading" && (
                <div className="model-progress">
                  <div style={{ width: `${model.progress ?? 0}%` }} />
                </div>
              )}
              <div className="model-actions">
                <button
                  className="secondary-action"
                  disabled={model.name === selectedModelName || !canChooseModelAsDefault(model)}
                  type="button"
                  onClick={() => onChooseDefaultModel(model.name)}
                >
                  {defaultModelActionLabel(model, selectedModelName)}
                </button>
                {model.status !== "ready" && (
                  <button type="button" onClick={() => onStartModelDownload(model.name)}>
                    {modelDownloadActionLabel(model)}
                  </button>
                )}
              </div>
            </article>
          ))}
          {!models && <p>Проверяю модели</p>}
        </div>
      </section>
    </div>
  );
}
