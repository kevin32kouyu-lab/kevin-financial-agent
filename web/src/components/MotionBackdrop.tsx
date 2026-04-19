/** 全局动态背景：提供粒子、流线和光晕的视觉层。 */
import { useEffect, useRef } from "react";

type MotionLevel = "high" | "low";

interface MotionBackdropProps {
  enabled: boolean;
  level?: MotionLevel;
  className?: string;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
}

/** 渲染动态背景粒子层。 */
export function MotionBackdrop({ enabled, level = "high", className }: MotionBackdropProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const shouldAnimate = enabled && !reducedMotion;
    const particleCount = shouldAnimate ? (level === "high" ? 124 : 42) : 18;
    const speedFactor = shouldAnimate ? (level === "high" ? 1.18 : 0.62) : 0.15;
    const linkDistance = level === "high" ? 190 : 132;

    const particles: Particle[] = [];

    function resize() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * ratio);
      canvas.height = Math.floor(window.innerHeight * ratio);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function createParticles() {
      particles.length = 0;
      for (let i = 0; i < particleCount; i += 1) {
        particles.push({
          x: Math.random() * window.innerWidth,
          y: Math.random() * window.innerHeight,
          vx: (Math.random() - 0.5) * 0.32 * speedFactor,
          vy: (Math.random() - 0.5) * 0.32 * speedFactor,
          radius: shouldAnimate ? Math.random() * 1.8 + 0.8 : Math.random() * 1.4 + 0.5,
          alpha: shouldAnimate ? Math.random() * 0.52 + 0.2 : Math.random() * 0.22 + 0.08,
        });
      }
    }

    function drawBackground(time: number) {
      context.clearRect(0, 0, window.innerWidth, window.innerHeight);

      const gradient = context.createLinearGradient(0, 0, window.innerWidth, window.innerHeight);
      gradient.addColorStop(0, "rgba(17, 40, 71, 0.20)");
      gradient.addColorStop(0.55, "rgba(9, 22, 40, 0.06)");
      gradient.addColorStop(1, "rgba(19, 56, 90, 0.16)");
      context.fillStyle = gradient;
      context.fillRect(0, 0, window.innerWidth, window.innerHeight);

      if (shouldAnimate) {
        const sweep = (Math.sin(time / 3500) + 1) / 2;
        const sweepX = sweep * window.innerWidth;
        const reverseSweep = (Math.cos(time / 4200) + 1) / 2;
        const reverseX = reverseSweep * window.innerWidth;
        context.strokeStyle = "rgba(94, 168, 255, 0.17)";
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(sweepX - 160, 0);
        context.lineTo(sweepX + 220, window.innerHeight);
        context.stroke();

        context.strokeStyle = "rgba(104, 229, 215, 0.11)";
        context.beginPath();
        context.moveTo(reverseX + 180, 0);
        context.lineTo(reverseX - 120, window.innerHeight);
        context.stroke();
      }
    }

    function drawParticles(time: number) {
      for (let i = 0; i < particles.length; i += 1) {
        const point = particles[i];

        if (shouldAnimate) {
          point.x += point.vx;
          point.y += point.vy;
        }

        if (point.x < -16) point.x = window.innerWidth + 16;
        if (point.x > window.innerWidth + 16) point.x = -16;
        if (point.y < -16) point.y = window.innerHeight + 16;
        if (point.y > window.innerHeight + 16) point.y = -16;

        const pulse = shouldAnimate ? (Math.sin(time / 1200 + i * 0.33) + 1) / 2 : 0.45;
        context.beginPath();
        context.fillStyle = `rgba(144, 210, 255, ${Math.min(0.86, point.alpha + pulse * 0.24)})`;
        context.arc(point.x, point.y, point.radius + pulse * 0.9, 0, Math.PI * 2);
        context.fill();
      }

      context.lineWidth = 1;
      for (let i = 0; i < particles.length; i += 1) {
        for (let j = i + 1; j < particles.length; j += 1) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          if (distance > linkDistance) continue;
          const opacity = (1 - distance / linkDistance) * (shouldAnimate ? 0.15 : 0.08);
          context.strokeStyle = `rgba(118, 198, 255, ${opacity})`;
          context.beginPath();
          context.moveTo(a.x, a.y);
          context.lineTo(b.x, b.y);
          context.stroke();
        }
      }
    }

    function render(time: number) {
      drawBackground(time);
      drawParticles(time);
      frameRef.current = requestAnimationFrame(render);
    }

    resize();
    createParticles();
    frameRef.current = requestAnimationFrame(render);

    function onResize() {
      resize();
      createParticles();
    }

    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [enabled, level]);

  return (
    <div className={`motion-backdrop ${className || ""}`} data-enabled={enabled ? "true" : "false"}>
      <canvas ref={canvasRef} className="motion-backdrop-canvas" />
      <span className="motion-halo motion-halo-a" />
      <span className="motion-halo motion-halo-b" />
      <span className="motion-halo motion-halo-c" />
    </div>
  );
}
