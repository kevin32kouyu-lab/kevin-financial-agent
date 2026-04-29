/** 首页视图：提供品牌主视觉、使用引导和终端入口。 */
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Globe, LineChart, ShieldCheck, Sparkles } from "lucide-react";

import { MotionBackdrop } from "../components/MotionBackdrop";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { readLocale, syncDocumentLocale, writeLocale } from "../lib/locale";
import { readMotionEnabled, writeMotionEnabled } from "../lib/motion";

const LANDING_COPY = {
  zh: {
    brand: "Financial Agent",
    title: "问一句，得到可验证的投资研究",
    subtitle: "输入你的资金、风险和关注标的，系统会给出结论、风险、依据和可导出的正式报告。",
    ctaPrimary: "开始研究",
    ctaSecondary: "看示例",
    heroLabel: "面向真实决策的研究入口",
    heroMetrics: [
      { label: "研究语言", value: "中英双语" },
      { label: "输出", value: "结论 + 回测 + PDF" },
      { label: "能力", value: "Agent + RAG + 校验" },
    ],
    howTitle: "三步开始",
    steps: [
      "写下投资问题",
      "先看结论与风险",
      "再看回测与报告",
    ],
    valueCards: [
      {
        title: "问一句",
        text: "自然语言直接发起研究。",
      },
      {
        title: "看结论",
        text: "先看到建议，再决定要不要下钻。",
      },
      {
        title: "可验证",
        text: "证据、校验和回测都能回看。",
      },
    ],
    sceneTickets: ["需求已解析", "覆盖已同步", "风险已锁定", "回放已就绪"],
  },
  en: {
    brand: "Financial Agent",
    title: "Ask once, get verifiable investment research",
    subtitle: "Share your capital, risk, and target names. The system returns a verdict, risk view, evidence trail, and export-ready report.",
    ctaPrimary: "Open Research Terminal",
    ctaSecondary: "See example",
    heroLabel: "A research entry built for real decisions",
    heroMetrics: [
      { label: "Language", value: "Bilingual" },
      { label: "Output", value: "Verdict + Backtest + PDF" },
      { label: "Engine", value: "Agent + RAG + Validation" },
    ],
    howTitle: "Start in 3 Steps",
    steps: [
      "Ask your question",
      "See verdict and risk",
      "Review backtest and report",
    ],
    valueCards: [
      {
        title: "Ask once",
        text: "Start research directly in natural language.",
      },
      {
        title: "See verdict",
        text: "Read the answer first, then drill deeper if needed.",
      },
      {
        title: "Verify before acting",
        text: "Evidence, validation, and backtest stay within the same flow.",
      },
    ],
    sceneTickets: ["Mandate parsed", "Coverage synced", "Risk locked", "Replay ready"],
  },
} as const;

/** 首页主组件。 */
export function LandingView() {
  const [locale, setLocale] = useState<"zh" | "en">(readLocale);
  const [motionEnabled, setMotionEnabled] = useState<boolean>(() => readMotionEnabled());
  const [motionLevel, setMotionLevel] = useState<"high" | "low">(() => (readMotionEnabled() ? "high" : "low"));
  const copy = useMemo(() => LANDING_COPY[locale], [locale]);
  const proofIcons = [LineChart, ShieldCheck, Sparkles] as const;

  useEffect(() => {
    writeLocale(locale);
    syncDocumentLocale(locale);
    if (typeof document !== "undefined") {
      document.title = copy.title;
    }
  }, [locale, copy.title]);

  useEffect(() => {
    writeMotionEnabled(motionEnabled);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-motion", motionEnabled ? "on" : "off");
    }
  }, [motionEnabled]);

  /** 切换动效开关。 */
  function toggleMotion() {
    setMotionEnabled((value) => {
      const next = !value;
      setMotionLevel(next ? "high" : "low");
      return next;
    });
  }

  return (
    <div className="landing-shell">
      <MotionBackdrop enabled={motionEnabled} level={motionLevel} className="landing-motion" />
      <div className="landing-flow-bg" aria-hidden="true">
        <span className="flow-orb orb-a" />
        <span className="flow-orb orb-b" />
        <span className="flow-orb orb-c" />
        <span className="flow-grid" />
      </div>

      <header className="landing-topbar">
        <div className="landing-brand">
          <Sparkles size={16} />
          <span>{copy.brand}</span>
        </div>
        <div className="landing-top-actions">
          <Button variant="secondary" size="sm" className="landing-top-button" onClick={toggleMotion}>
            <Sparkles size={14} />
            {locale === "zh" ? `动效${motionEnabled ? "开启" : "关闭"}` : `Motion ${motionEnabled ? "On" : "Off"}`}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="landing-top-button"
            onClick={() => setLocale((value) => (value === "zh" ? "en" : "zh"))}
          >
            <Globe size={14} />
            {locale === "zh" ? "English" : "中文"}
          </Button>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero-panel surface-appear" data-delay="1">
          <div className="landing-hero-copy">
            <Badge variant="secondary" className="landing-kicker surface-appear" data-delay="2">
              {copy.heroLabel}
            </Badge>
            <h1 className="surface-appear" data-delay="2">{copy.title}</h1>
            <p className="landing-subtitle surface-appear" data-delay="3">{copy.subtitle}</p>
            <div className="landing-actions surface-appear" data-delay="5">
              <Button size="lg" className="landing-primary-cta" asChild>
                <a href="/terminal">
                  {copy.ctaPrimary}
                  <ArrowRight size={16} />
                </a>
              </Button>
              <Button variant="secondary" size="lg" className="landing-secondary-cta" asChild>
                <a href="/terminal?guide=demo">{copy.ctaSecondary}</a>
              </Button>
            </div>
            <div className="landing-hero-metrics surface-appear" data-delay="6">
              {copy.heroMetrics.map((item) => (
                <div key={item.label} className="landing-signal-metric">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="landing-hero-scene surface-appear" data-delay="4" aria-hidden="true">
            <div className="landing-scene-shell">
              <span className="landing-scene-grid" />
              <span className="landing-scene-beam beam-a" />
              <span className="landing-scene-beam beam-b" />
              <span className="landing-scene-orbit orbit-a" />
              <span className="landing-scene-orbit orbit-b" />
              <span className="landing-scene-core" />
              <div className="landing-scene-stack">
                {copy.sceneTickets.map((item, index) => (
                  <div
                    key={item}
                    className="landing-scene-ticket"
                    style={{ animationDelay: `${index * 120}ms` }}
                  >
                    <span />
                    <strong>{item}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="landing-story-band surface-appear" data-delay="6">
          <article className="landing-step-rail">
            <p className="eyebrow">{copy.howTitle}</p>
            <h2>{copy.howTitle}</h2>
            <ol className="landing-step-list">
              {copy.steps.map((item, index) => (
                <li key={item} className="landing-step-item">
                  <span>{index + 1}</span>
                  <div>
                    <strong>{item}</strong>
                  </div>
                </li>
              ))}
            </ol>
          </article>
          <article className="landing-story-copy">
            <p className="eyebrow">{copy.heroLabel}</p>
            <h2>{copy.ctaPrimary}</h2>
            <p>{copy.subtitle}</p>
          </article>
        </section>

        <section className="landing-proof-strip surface-appear" data-delay="7">
          {copy.valueCards.map((item, index) => {
            const Icon = proofIcons[index] || Sparkles;
            return (
              <article key={item.title} className="landing-proof-item">
                <div className="landing-proof-icon">
                  <Icon size={18} />
                </div>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            );
          })}
        </section>
      </main>
    </div>
  );
}
