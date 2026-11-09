"use client";
import { useRef, type ReactNode } from "react";
import { calendarSwipe } from "@/lib/calendar-navigation";

export function CalendarSwipe({
  children,
  className,
  onNavigate,
}: {
  children: ReactNode;
  className: string;
  onNavigate: (direction: number) => void;
}) {
  const gesture = useRef<{ x: number; y: number; time: number } | null>(null);
  const suppressClickUntil = useRef(0);
  return (
    <div
      className={className}
      onTouchStart={(event) => {
        const touch = event.touches[0];
        // Leave edge gestures to browser back/forward navigation.
        gesture.current =
          event.touches.length === 1 && touch.clientX > 24 && touch.clientX < window.innerWidth - 24
            ? { x: touch.clientX, y: touch.clientY, time: event.timeStamp }
            : null;
      }}
      onTouchMove={(event) => {
        const initial = gesture.current;
        if (!initial) return;
        const touch = event.touches[0];
        if (
          event.touches.length !== 1 ||
          (Math.abs(touch.clientY - initial.y) > 12 &&
            Math.abs(touch.clientY - initial.y) > Math.abs(touch.clientX - initial.x))
        )
          gesture.current = null;
      }}
      onTouchCancel={() => {
        gesture.current = null;
      }}
      onTouchEnd={(event) => {
        const initial = gesture.current;
        gesture.current = null;
        if (!initial || event.touches.length || event.changedTouches.length !== 1) return;
        const touch = event.changedTouches[0];
        const direction = calendarSwipe(
          touch.clientX - initial.x,
          touch.clientY - initial.y,
          event.timeStamp - initial.time,
        );
        if (direction) {
          suppressClickUntil.current = performance.now() + 500;
          onNavigate(direction);
        }
      }}
      onClickCapture={(event) => {
        if (event.detail !== 0 && performance.now() < suppressClickUntil.current) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
    >
      {children}
    </div>
  );
}
