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
    brand: "ROSE Capital Research",
    title: "金融研究 Agent",
    subtitle: "让用户先看到判断，再决定要不要继续读完整条研究链路。",
    description:
      "把自然语言需求、股票筛选、多源数据、审计校验、回测结果和正式报告，整理成一套更适合展示、也更适合真实投研沟通的前台体验。",
    ctaPrimary: "进入研究终端",
    ctaSecondary: "查看终端示例",
    heroLabel: "机构级研究前台",
    heroMetrics: [
      { label: "研究语言", value: "中英双语" },
      { label: "研究路径", value: "研究 + 回测 + 导出" },
      { label: "数据链路", value: "多源聚合" },
    ],
    introTitle: "这个首页现在要解决什么",
    introBody:
      "它不再只是一个跳转页，而是先帮助用户理解：这套系统适合什么场景、怎么开始、产出会是什么样子。",
    howTitle: "三步开始",
    steps: [
      "输入资金规模、风险偏好、期限和关注标的",
      "先看结论、风险一句话和下一步动作",
      "再看候选池、回测曲线和正式报告导出",
    ],
    valueCards: [
      {
        title: "先交结论",
        text: "首屏先给判断，不让用户先被过程信息拖住。",
      },
      {
        title: "链路可解释",
        text: "每个建议都能追溯到数据来源、时间点和执行上下文。",
      },
      {
        title: "同页可验证",
        text: "研究、回测、导出都在同一条任务流里完成。",
      },
    ],
    footer: "当前版本已按桌面演示场景优化，并保留基础移动端适配。",
    sceneTickets: ["需求已解析", "覆盖已同步", "风险已锁定", "回放已就绪"],
  },
  en: {
    brand: "ROSE Capital Research",
    title: "Financial Research Agent",
    subtitle: "Let users see the decision first, then decide whether to read the full research chain.",
    description:
      "Bring natural-language intent, screening, multi-source data, audit checks, backtest output, and export-ready reports into one frontend that feels easier to present and easier to trust.",
    ctaPrimary: "Open Research Terminal",
    ctaSecondary: "See Terminal Example",
    heroLabel: "Institutional-grade research surface",
    heroMetrics: [
      { label: "Research language", value: "Bilingual" },
      { label: "Flow", value: "Research + Replay + Export" },
      { label: "Data chain", value: "Multi-source" },
    ],
    introTitle: "What this homepage should do now",
    introBody:
      "This is no longer a simple jump page. It should first help users understand what the product is for, how to start, and what kind of result they will get.",
    howTitle: "Start in 3 Steps",
    steps: [
      "Enter capital, risk preference, horizon, and target symbols",
      "Read verdict, one-line risk view, and the next action first",
      "Then review candidates, replay curves, and export the formal report",
    ],
    valueCards: [
      {
        title: "Verdict first",
        text: "The first screen gives the decision before the process detail takes over.",
      },
      {
        title: "Traceable chain",
        text: "Every recommendation can be traced to source, timing, and execution context.",
      },
      {
        title: "Verifiable in one flow",
        text: "Research, replay, and export stay inside one task flow.",
      },
    ],
    footer: "This version is tuned for desktop demos and keeps baseline mobile support.",
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
            <p className="landing-description surface-appear" data-delay="4">{copy.description}</p>
            <div className="landing-actions surface-appear" data-delay="5">
              <Button size="lg" className="landing-primary-cta" asChild>
                <a href="/terminal">
                  {copy.ctaPrimary}
                  <ArrowRight size={16} />
                </a>
              </Button>
              <Button variant="secondary" size="lg" className="landing-secondary-cta" asChild>
                <a href="/terminal#terminal-modes">{copy.ctaSecondary}</a>
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
          <article className="landing-story-copy">
            <p className="eyebrow">{copy.introTitle}</p>
            <h2>{copy.introTitle}</h2>
            <p>{copy.introBody}</p>
          </article>
          <article className="landing-step-rail">
            <p className="eyebrow">{copy.howTitle}</p>
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

        <p className="landing-footer-note">{copy.footer}</p>
      </main>
    </div>
  );
}
