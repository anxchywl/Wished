"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "@/lib/i18n/useTranslation";

type BirthdayPickerProps = {
  open: boolean;
  initial?: string | null;
  onClose: () => void;
  onSave: (date: string) => void;
  onClear?: () => void;
};

const currentYear = new Date().getFullYear();
const itemHeight = 40;
const defaultBirthday = { year: 2007, month: 11, day: 22 };

/**
 * birthday date picker bottom sheet
 */
export function BirthdayPicker({ open, initial, onClose, onSave, onClear }: BirthdayPickerProps) {
  const { t } = useTranslation();
  const backdropRef = useRef<HTMLDivElement>(null);
  const yearRef = useRef<HTMLDivElement>(null);
  const monthRef = useRef<HTMLDivElement>(null);
  const dayRef = useRef<HTMLDivElement>(null);

  const parseInitial = () => {
    if (initial) {
      const parts = initial.split("-");
      if (parts.length === 3) {
        return {
          year: parseInt(parts[0], 10),
          month: parseInt(parts[1], 10),
          day: parseInt(parts[2], 10),
        };
      }
    }
    return defaultBirthday;
  };

  const [year, setYear] = useState(parseInitial().year);
  const [month, setMonth] = useState(parseInitial().month);
  const [day, setDay] = useState(parseInitial().day);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open) {
      const p = parseInitial();
      setYear(p.year);
      setMonth(p.month);
      setDay(p.day);
      requestAnimationFrame(() => {
        setVisible(true);
        scrollToValue(yearRef.current, currentYear - p.year);
        scrollToValue(monthRef.current, p.month - 1);
        scrollToValue(dayRef.current, p.day - 1);
      });
    } else {
      setVisible(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial]);

  const daysInMonth = new Date(year, month, 0).getDate();
  const months = t("months").split(",");
  const years = Array.from({ length: 105 }, (_, i) => currentYear - i);
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  useEffect(() => {
    if (day <= daysInMonth) return;
    setDay(daysInMonth);
    scrollToValue(dayRef.current, daysInMonth - 1);
  }, [day, daysInMonth]);

  function scrollToValue(element: HTMLDivElement | null, index: number) {
    element?.scrollTo({ top: index * itemHeight });
  }

  function handleColumnScroll<T>(
    element: HTMLDivElement | null,
    items: T[],
    onChange: (item: T) => void,
  ) {
    if (!element) return;
    const index = Math.min(items.length - 1, Math.max(0, Math.round(element.scrollTop / itemHeight)));
    onChange(items[index]);
  }

  function handleSave() {
    const mm = String(month).padStart(2, "0");
    const dd = String(Math.min(day, daysInMonth)).padStart(2, "0");
    onSave(`${year}-${mm}-${dd}`);
  }

  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === backdropRef.current) onClose();
  }

  if (!open) return null;

  const picker = (
    <div
      ref={backdropRef}
      className={`birthday-picker-backdrop ${visible ? "visible" : ""}`}
      onClick={handleBackdropClick}
      aria-modal="true"
      role="dialog"
    >
      <div className={`birthday-picker-sheet ${visible ? "visible" : ""}`}>
        <div className="birthday-picker-handle" />
        <div className="birthday-picker-header">
          {initial && onClear ? (
            <button
              className="birthday-picker-clear"
              type="button"
              onClick={onClear}
              aria-label={t("removeBirthday")}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" d="M7 12h10" />
              </svg>
            </button>
          ) : (
            <span className="birthday-picker-header-spacer" />
          )}
          <p className="birthday-picker-title">{t("birthday")}</p>
          <span className="birthday-picker-header-spacer" />
        </div>

        <div className="birthday-picker-wheel" aria-label="Birthday chooser">
          <div className="birthday-picker-selection" />

          <div
            ref={dayRef}
            className="birthday-picker-wheel-col"
            aria-label="Day"
            onScroll={(event) => handleColumnScroll(event.currentTarget, days, setDay)}
          >
            {days.map((item) => (
                <button
                  className={`birthday-picker-wheel-item${item === day ? " active" : ""}`}
                  key={item}
                  onClick={() => {
                    setDay(item);
                    scrollToValue(dayRef.current, item - 1);
                  }}
                  type="button"
                >
                  {item}
                </button>
            ))}
          </div>

          <div
            ref={monthRef}
            className="birthday-picker-wheel-col"
            aria-label="Month"
            onScroll={(event) => {
              handleColumnScroll(event.currentTarget, months, (item) => setMonth(months.indexOf(item) + 1));
            }}
          >
            {months.map((item, index) => (
                <button
                  className={`birthday-picker-wheel-item${index + 1 === month ? " active" : ""}`}
                  key={item}
                  onClick={() => {
                    setMonth(index + 1);
                    scrollToValue(monthRef.current, index);
                  }}
                  type="button"
                >
                  {item}
                </button>
            ))}
          </div>

          <div
            ref={yearRef}
            className="birthday-picker-wheel-col"
            aria-label="Year"
            onScroll={(event) => handleColumnScroll(event.currentTarget, years, setYear)}
          >
            {years.map((item) => (
                <button
                  className={`birthday-picker-wheel-item${item === year ? " active" : ""}`}
                  key={item}
                  onClick={() => {
                    setYear(item);
                    scrollToValue(yearRef.current, years.indexOf(item));
                  }}
                  type="button"
                >
                  {item}
                </button>
            ))}
          </div>
        </div>

        <div className="birthday-picker-actions">
          <button className="birthday-picker-cancel" type="button" onClick={onClose}>
            {t("cancelButton") ?? "Cancel"}
          </button>
          <button
            className="birthday-picker-save"
            type="button"
            onClick={handleSave}
          >
            {t("apply") ?? "Apply"}
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(picker, document.body) : null;
}
