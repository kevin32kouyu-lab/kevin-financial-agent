import { formatDateTime, formatJson, summarizeValue, repairText } from "../lib/format";
import type { ArtifactRecord, Locale } from "../lib/types";
import type { LocalePack } from "../lib/i18n";

interface ArtifactPanelProps {
  locale: Locale;
  copy: LocalePack;
  artifacts: ArtifactRecord[];
  selectedArtifactId: number | null;
  selectedKind: string;
  onSelectArtifact: (artifactId: number) => void;
  onSelectKind: (kind: string) => void;
}

export function ArtifactPanel({
  locale,
  copy,
  artifacts,
  selectedArtifactId,
  selectedKind,
  onSelectArtifact,
  onSelectKind,
}: ArtifactPanelProps) {
  const kinds = ["all", ...Array.from(new Set(artifacts.map((artifact) => artifact.kind)))];
  const visibleArtifacts =
    selectedKind === "all" ? artifacts : artifacts.filter((artifact) => artifact.kind === selectedKind);
  const selectedArtifact =
    visibleArtifacts.find((artifact) => artifact.id === selectedArtifactId) || visibleArtifacts[0] || null;

  return (
    <section className="panel-surface debug-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "产物" : "Artifacts"}</p>
          <h2>{copy.debug.artifacts}</h2>
        </div>
        <label className="field compact-field">
          <span>{copy.debug.artifactType}</span>
          <select value={selectedKind} onChange={(event) => onSelectKind(event.target.value)}>
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="artifact-layout">
        <div className="artifact-list">
          {visibleArtifacts.length ? (
            visibleArtifacts.map((artifact) => (
              <button
                key={artifact.id}
                type="button"
                className={artifact.id === selectedArtifact?.id ? "artifact-item active" : "artifact-item"}
                onClick={() => onSelectArtifact(artifact.id)}
              >
                <div className="artifact-title-row">
                  <strong>
                    {artifact.kind} / {repairText(artifact.name)}
                  </strong>
                </div>
                <p>{summarizeValue(artifact.content, locale)}</p>
                <span>{formatDateTime(artifact.updated_at, locale)}</span>
              </button>
            ))
          ) : (
            <div className="empty-state small">{copy.debug.noArtifacts}</div>
          )}
        </div>

        <div className="artifact-preview">
          {selectedArtifact ? (
            <>
              <div className="mini-card">
                <h3>
                  {selectedArtifact.kind} / {repairText(selectedArtifact.name)}
                </h3>
                <p>{locale === "zh" ? "创建时间" : "Created"}: {formatDateTime(selectedArtifact.created_at, locale)}</p>
                <p>{locale === "zh" ? "更新时间" : "Updated"}: {formatDateTime(selectedArtifact.updated_at, locale)}</p>
              </div>
              <pre className="json-viewer">{formatJson(selectedArtifact.content)}</pre>
            </>
          ) : (
            <div className="empty-state small">{copy.debug.selectArtifact}</div>
          )}
        </div>
      </div>
    </section>
  );
}
