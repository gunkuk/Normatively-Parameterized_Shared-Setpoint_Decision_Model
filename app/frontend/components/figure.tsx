"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "./ui/button";

export function FigureFrame({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  const frame = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!focused) return;
    const hidden: [HTMLElement, boolean][] = [];
    let node: HTMLElement | null = frame.current;
    while (node && node !== document.body) {
      const parent: HTMLElement | null = node.parentElement;
      for (const sibling of Array.from(parent?.children ?? [])) {
        if (sibling !== node && sibling instanceof HTMLElement) {
          hidden.push([sibling, sibling.inert]);
          sibling.inert = true;
        }
      }
      node = parent;
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Tab") {
        const items = Array.from(
          frame.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled), summary, [tabindex="0"]',
          ) ?? [],
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
      if (event.key === "Escape") {
        setFocused(false);
        toggle.current?.focus();
      }
    };
    window.addEventListener("keydown", escape);
    return () => {
      hidden.forEach(([element, inert]) => {
        element.inert = inert;
      });
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", escape);
    };
  }, [focused]);
  return (
    <section
      ref={frame}
      role={focused ? "dialog" : undefined}
      aria-modal={focused ? true : undefined}
      className={`figure-frame ${focused ? "figure-focused" : ""}`}
      aria-label={`${title} Figure 영역`}
    >
      <div className="figure-toolbar">
        <span>{title} · Figure 보기에서는 이 패널만 표시합니다.</span>
        <Button
          ref={toggle}
          variant="outline"
          aria-pressed={focused}
          onClick={() => setFocused(!focused)}
        >
          {focused ? "기본 화면으로 돌아가기" : `${title} Figure 보기`}
        </Button>
      </div>
      <div className="figure-paper" data-figure={title}>
        {children}
      </div>
    </section>
  );
}
