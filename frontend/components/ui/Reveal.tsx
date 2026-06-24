"use client";

import { useEffect, useRef, useState } from "react";

export function Reveal({
  children,
  className,
  delay = 0
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setMounted(true);

    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReduced) {
      setReduced(true);
      setRevealed(true);
      return;
    }

    const node = ref.current;
    if (!node) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setRevealed(true);
            observer.disconnect();
            break;
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 }
    );

    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  // Before mount (server render + no-JS) and for reduced motion, render fully
  // visible with no transition so content is never hidden behind animation.
  const animate = mounted && !reduced;
  const hidden = animate && !revealed;

  return (
    <div
      ref={ref}
      className={className}
      style={
        animate
          ? {
              opacity: hidden ? 0 : 1,
              transform: hidden ? "translateY(12px)" : "translateY(0)",
              transition: "opacity 500ms ease-out, transform 500ms ease-out",
              transitionDelay: delay ? `${delay}ms` : undefined,
              willChange: "opacity, transform"
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}
