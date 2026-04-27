/** 终端产品引导：首次进入时用弹窗和高亮步骤说明主要功能区。 */
import { type CSSProperties, useEffect, useId, useMemo, useState } from "react";

import type { LocalePack } from "../../lib/i18n";
import { hasCompletedProductTour, writeProductTourCompleted } from "../../lib/productTour";
import type { TerminalPage } from "../../hooks/useTerminalNavigation";
import { Button } from "../ui/button";

type ProductTourCopy = LocalePack["terminal"]["productGuide"];

interface ProductTourProps {
  copy: ProductTourCopy;
  activeRunId: string | null;
  replaySignal: number;
  onNavigate: (page: TerminalPage, runId?: string | null, replace?: boolean) => void;
}

interface TargetBox {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface StepView {
  id: string;
  page: TerminalPage;
  targetId: string;
  title: string;
  body: string;
}

/** 约束弹窗位置，避免贴到屏幕边缘。 */
function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

/** 根据目标元素计算引导卡片位置。 */
function buildCardStyle(target: TargetBox | null): CSSProperties {
  if (!target || typeof window === "undefined") return {};
  const width = Math.min(420, window.innerWidth - 32);
  const left = clamp(target.left + target.width / 2 - width / 2, 16, window.innerWidth - width - 16);
  const preferBelow = target.top + target.height + 18;
  const preferAbove = target.top - 260;
  const top = preferBelow + 240 < window.innerHeight ? preferBelow : clamp(preferAbove, 16, window.innerHeight - 280);
  return { width, left, top };
}

/** 渲染首次欢迎与分步功能区引导。 */
export function ProductTour({ copy, activeRunId, replaySignal, onNavigate }: ProductTourProps) {
  const [mode, setMode] = useState<"hidden" | "welcome" | "steps">("hidden");
  const [stepIndex, setStepIndex] = useState(0);
  const [targetBox, setTargetBox] = useState<TargetBox | null>(null);
  const titleId = useId();

  const steps = useMemo<StepView[]>(
    () => [
      { id: "ask", page: "ask", targetId: "terminal-ask-panel", ...copy.steps.ask },
      { id: "progress", page: "ask", targetId: "terminal-progress-card", ...copy.steps.progress },
      { id: "conclusion", page: "conclusion", targetId: "terminal-conclusion-page", ...copy.steps.conclusion },
      { id: "backtest", page: "backtest", targetId: "terminal-backtest-page", ...copy.steps.backtest },
      { id: "archive", page: "archive", targetId: "terminal-archive-page", ...copy.steps.archive },
      { id: "account", page: "archive", targetId: "terminal-account-entry", ...copy.steps.account },
    ],
    [copy.steps],
  );

  const activeStep = steps[stepIndex];

  useEffect(() => {
    if (!hasCompletedProductTour()) {
      setMode("welcome");
    }
  }, []);

  useEffect(() => {
    if (replaySignal > 0) {
      setStepIndex(0);
      setMode("welcome");
    }
  }, [replaySignal]);

  useEffect(() => {
    if (mode !== "steps" || !activeStep) return;
    onNavigate(activeStep.page, activeRunId, true);
  }, [activeRunId, activeStep, mode, onNavigate]);

  useEffect(() => {
    if (mode !== "steps" || !activeStep) {
      setTargetBox(null);
      return;
    }

    let frame = 0;
    let attempts = 0;
    let hasAligned = false;
    const measureTarget = () => {
      frame = 0;
      const element = document.querySelector<HTMLElement>(`[data-tour-id="${activeStep.targetId}"]`);
      if (!element) {
        if (attempts < 8) {
          attempts += 1;
          frame = window.requestAnimationFrame(measureTarget);
          return;
        }
        setTargetBox(null);
        return;
      }
      if (!hasAligned) {
        hasAligned = true;
        element.scrollIntoView({ behavior: "auto", block: "center", inline: "nearest" });
      }
      const rect = element.getBoundingClientRect();
      setTargetBox({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    };
    const scheduleMeasure = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(measureTarget);
    };

    scheduleMeasure();
    const listenerOptions: AddEventListenerOptions = { passive: true, capture: true };
    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("scroll", scheduleMeasure, listenerOptions);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, listenerOptions);
    };
  }, [activeStep, mode]);

  useEffect(() => {
    if (mode === "hidden") return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        finishTour();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  /** 结束引导并写入本地状态。 */
  function finishTour() {
    writeProductTourCompleted();
    setMode("hidden");
  }

  /** 从欢迎弹窗进入第一步。 */
  function startSteps() {
    setStepIndex(0);
    setMode("steps");
  }

  /** 前进到下一步，最后一步则完成引导。 */
  function goNext() {
    if (stepIndex >= steps.length - 1) {
      finishTour();
      return;
    }
    setStepIndex((value) => value + 1);
  }

  /** 回到上一步，第一步则回到欢迎弹窗。 */
  function goPrevious() {
    if (stepIndex === 0) {
      setMode("welcome");
      return;
    }
    setStepIndex((value) => value - 1);
  }

  if (mode === "hidden") return null;

  if (mode === "welcome") {
    return (
      <div className="product-tour-overlay product-tour-overlay-center">
        <section className="product-tour-dialog product-tour-welcome" role="dialog" aria-modal="true" aria-labelledby={titleId}>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h2 id={titleId}>{copy.welcomeTitle}</h2>
          <p className="lead-copy">{copy.welcomeBody}</p>
          <div className="product-tour-proof-grid">
            {copy.proofPoints.map((item) => (
              <article key={item.title} className="mini-card">
                <span className="mini-label">{item.title}</span>
                <strong>{item.body}</strong>
              </article>
            ))}
          </div>
          <div className="button-row product-tour-actions">
            <Button type="button" onClick={startSteps}>
              {copy.start}
            </Button>
            <Button type="button" variant="secondary" onClick={finishTour}>
              {copy.skip}
            </Button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="product-tour-overlay">
      {targetBox ? (
        <div
          className="product-tour-highlight"
          style={{
            top: targetBox.top - 8,
            left: targetBox.left - 8,
            width: targetBox.width + 16,
            height: targetBox.height + 16,
          }}
        />
      ) : null}
      <section
        className="product-tour-dialog product-tour-step-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={buildCardStyle(targetBox)}
      >
        <div className="product-tour-step-meta">
          <span>
            {copy.stepLabel} {stepIndex + 1}/{steps.length}
          </span>
        </div>
        <h2 id={titleId}>{activeStep.title}</h2>
        <p className="lead-copy">{activeStep.body}</p>
        <div className="product-tour-dots" aria-hidden="true">
          {steps.map((item, index) => (
            <span key={item.id} className={index === stepIndex ? "active" : ""} />
          ))}
        </div>
        <div className="button-row product-tour-actions">
          <Button type="button" variant="secondary" onClick={finishTour}>
            {copy.skip}
          </Button>
          <Button type="button" variant="secondary" onClick={goPrevious}>
            {copy.prev}
          </Button>
          <Button type="button" onClick={goNext}>
            {stepIndex >= steps.length - 1 ? copy.done : copy.next}
          </Button>
        </div>
      </section>
    </div>
  );
}
