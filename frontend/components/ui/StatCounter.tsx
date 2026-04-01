"use client";

import { animate, useInView } from "framer-motion";
import { useEffect, useRef } from "react";

export function StatCounter({ value, label }: { value: number; label: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const numberRef = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView || !numberRef.current) {
      return;
    }
    const controls = animate(0, value, {
      duration: 1.4,
      onUpdate(latest) {
        if (numberRef.current) {
          numberRef.current.textContent = Math.round(latest).toLocaleString();
        }
      }
    });

    return () => controls.stop();
  }, [inView, value]);

  return (
    <div ref={ref} className="min-w-[180px]">
      <div className="font-[var(--font-display)] text-[36px] leading-none">
        <span ref={numberRef}>0</span>
      </div>
      <div className="mono mt-3">{label}</div>
    </div>
  );
}

