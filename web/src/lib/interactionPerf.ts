/** 交互性能观察：开发环境下记录点击到下一帧渲染完成的大致耗时。 */
export function markUiInteraction(label: string): () => void {
  if (!import.meta.env.DEV || typeof window === "undefined" || typeof window.performance === "undefined") {
    return () => {};
  }
  const startedAt = window.performance.now();
  return () => {
    window.requestAnimationFrame(() => {
      const elapsed = Math.round(window.performance.now() - startedAt);
      // 只在本地开发输出，用来判断卡顿来自渲染还是接口等待。
      console.debug(`[perf] ${label}: ${elapsed}ms`);
    });
  };
}
