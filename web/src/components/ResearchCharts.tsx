import { formatPercent, formatScore, repairText } from "../lib/format";
import type { Locale } from "../lib/types";
import type { LocalePack } from "../lib/i18n";

type GenericRecord = Record<string, unknown>;

interface ResearchChartsProps {
  locale: Locale;
  copy: LocalePack;
  ranking: GenericRecord[];
  dimensions: GenericRecord[];
  allocation: GenericRecord[];
}

function toNumber(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : 0;
}

function toText(value: unknown, fallback = "N/A"): string {
  return repairText(value, fallback);
}

function toneClass(score: number): string {
  if (score >= 75) {
    return "positive";
  }
  if (score >= 55) {
    return "neutral";
  }
  return "negative";
}

function heatColor(score: number): string {
  if (score >= 80) return "rgba(15, 118, 110, 0.18)";
  if (score >= 65) return "rgba(32, 94, 168, 0.18)";
  if (score >= 50) return "rgba(187, 140, 52, 0.18)";
  return "rgba(198, 77, 58, 0.18)";
}

function polarToCartesian(cx: number, cy: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleInRadians),
    y: cy + radius * Math.sin(angleInRadians),
  };
}

function describeArc(cx: number, cy: number, radius: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1;
  return ["M", start.x, start.y, "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(" ");
}

function RankingBars({ locale, copy, ranking }: Pick<ResearchChartsProps, "locale" | "copy" | "ranking">) {
  if (!ranking.length) {
    return <div className="chart-empty">{copy.report.empty}</div>;
  }

  const maxScore = Math.max(...ranking.map((item) => toNumber(item.score)), 1);
  return (
    <section className="chart-card">
      <div className="chart-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "候选排名" : "Ranking"}</p>
          <h3>{copy.report.scoreboard}</h3>
        </div>
      </div>

      <div className="ranking-bars">
        {ranking.map((item) => {
          const ticker = toText(item.ticker);
          const score = toNumber(item.score);
          const fit = toNumber(item.fit);
          return (
            <div key={ticker} className="ranking-row">
              <div className="ranking-label">
                <strong>{ticker}</strong>
                <span>{copy.report.labels.fit} {formatScore(fit)}</span>
              </div>
              <div className="ranking-track">
                <div className={`ranking-fill ${toneClass(score)}`} style={{ width: `${(score / maxScore) * 100}%` }} />
              </div>
              <div className="ranking-value">{formatScore(score)}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ScoreHeatmap({ locale, copy, dimensions }: Pick<ResearchChartsProps, "locale" | "copy" | "dimensions">) {
  if (!dimensions.length) {
    return <div className="chart-empty">{copy.report.empty}</div>;
  }

  const columns = [
    { key: "valuation", label: copy.report.labels.valuation },
    { key: "quality", label: copy.report.labels.quality },
    { key: "momentum", label: copy.report.labels.momentum },
    { key: "sentiment", label: locale === "zh" ? "情绪" : "Sentiment" },
    { key: "risk", label: copy.report.labels.risk },
    { key: "fit", label: copy.report.labels.fit },
  ];

  return (
    <section className="chart-card chart-wide">
      <div className="chart-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "因子矩阵" : "Factor matrix"}</p>
          <h3>{locale === "zh" ? "多维评分热力图" : "Multi-factor heatmap"}</h3>
        </div>
      </div>

      <div className="heatmap-table-wrap">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th>Ticker</th>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dimensions.map((item) => (
              <tr key={toText(item.ticker)}>
                <td>{toText(item.ticker)}</td>
                {columns.map((column) => {
                  const score = toNumber(item[column.key]);
                  return (
                    <td key={column.key}>
                      <span className="heat-cell" style={{ backgroundColor: heatColor(score) }}>
                        {formatScore(score)}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AllocationRing({ locale, copy, allocation }: Pick<ResearchChartsProps, "locale" | "copy" | "allocation">) {
  if (!allocation.length) {
    return (
      <section className="chart-card">
        <div className="chart-head">
          <div>
            <p className="eyebrow">{locale === "zh" ? "仓位计划" : "Allocation"}</p>
            <h3>{copy.report.execution}</h3>
          </div>
        </div>
        <div className="chart-empty">{copy.report.noAllocation}</div>
      </section>
    );
  }

  const palette = ["#153154", "#0f766e", "#c08b2f", "#b45309", "#c2410c"];
  let currentAngle = 0;

  return (
    <section className="chart-card">
      <div className="chart-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "仓位计划" : "Allocation"}</p>
          <h3>{copy.report.execution}</h3>
        </div>
      </div>

      <div className="allocation-layout">
        <svg viewBox="0 0 160 160" className="allocation-ring" aria-label="allocation chart">
          <circle cx="80" cy="80" r="48" fill="none" stroke="rgba(15, 23, 42, 0.08)" strokeWidth="18" />
          {allocation.map((item, index) => {
            const weight = Math.max(toNumber(item.weight), 0);
            const sliceAngle = (weight / 100) * 360;
            const path = describeArc(80, 80, 48, currentAngle, currentAngle + sliceAngle);
            const stroke = palette[index % palette.length];
            currentAngle += sliceAngle;
            return (
              <path
                key={toText(item.ticker)}
                d={path}
                fill="none"
                stroke={stroke}
                strokeWidth="18"
                strokeLinecap="round"
              />
            );
          })}
          <circle cx="80" cy="80" r="31" fill="#f8fafc" />
          <text x="80" y="73" textAnchor="middle" className="ring-label">
            {locale === "zh" ? "已分配" : "Allocated"}
          </text>
          <text x="80" y="92" textAnchor="middle" className="ring-value">
            {formatPercent(allocation.reduce((sum, item) => sum + toNumber(item.weight), 0))}
          </text>
        </svg>

        <div className="allocation-legend">
          {allocation.map((item, index) => (
            <div key={toText(item.ticker)} className="allocation-item">
              <span className="legend-swatch" style={{ backgroundColor: palette[index % palette.length] }} />
              <div>
                <strong>{toText(item.ticker)}</strong>
                <p>
                  {formatPercent(item.weight)} · {toText(item.verdict)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ResearchCharts({ locale, copy, ranking, dimensions, allocation }: ResearchChartsProps) {
  return (
    <section className="research-chart-grid">
      <RankingBars locale={locale} copy={copy} ranking={ranking} />
      <AllocationRing locale={locale} copy={copy} allocation={allocation} />
      <ScoreHeatmap locale={locale} copy={copy} dimensions={dimensions} />
    </section>
  );
}
