"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/api-client";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { useCreateGroupGiftMutation } from "@/features/group-gifts/hooks";
import type { GroupGiftCreatePayload } from "@/features/group-gifts/api";

type Props = {
  wishId: string;
  shareToken?: string | null;
  onClose: () => void;
};

const PHONE_RE = /^\+?[\d\s\-]{7,30}$/;

const ERROR_MAP: Record<string, string> = {
  group_gift_already_exists: "giftAlreadyExists",
  gift_not_active: "giftNotActive",
};

export function CreateGroupGiftSheet({ wishId, onClose }: Props) {
  const { t } = useTranslation();
  const [active, setActive] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [collectionType, setCollectionType] = useState<"immediate" | "commit" | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentPhone, setPaymentPhone] = useState("");
  const [paymentComment, setPaymentComment] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [submitError, setSubmitError] = useState("");

  const createMutation = useCreateGroupGiftMutation(wishId);

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  function handlePhoneBlur() {
    if (paymentPhone && !PHONE_RE.test(paymentPhone)) {
      setPhoneError(t("paymentPhoneLabel") + ": " + t("productUrlInvalid").replace("Kaspi, Wildberries, або Ozon", "").trim());
    } else {
      setPhoneError("");
    }
  }

  function validatePhone() {
    if (!PHONE_RE.test(paymentPhone)) {
      setPhoneError(t("paymentPhoneLabel") + " invalid");
      return false;
    }
    setPhoneError("");
    return true;
  }

  function handleSubmit() {
    if (!collectionType) return;
    if (!validatePhone()) return;

    const payload: GroupGiftCreatePayload = {
      collection_type: collectionType,
      payment_method: paymentMethod.trim(),
      payment_phone: paymentPhone.trim(),
      ...(paymentComment.trim() ? { payment_comment: paymentComment.trim() } : {}),
    };

    setSubmitError("");
    createMutation.mutate(payload, {
      onSuccess: () => handleClose(),
      onError: (err) => {
        if (err instanceof ApiError) {
          const detail = (err.payload as { detail?: string } | null)?.detail ?? "";
          const key = ERROR_MAP[detail];
          setSubmitError(key ? t(key as Parameters<typeof t>[0]) : detail || err.message);
        } else {
          setSubmitError(String(err));
        }
      },
    });
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet ${active ? "visible" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <h3 className="modal-title font-bold text-base mb-4 text-center">
          {t("createGroupGift")}
        </h3>

        {step === 1 ? (
          <div className="flex flex-col gap-3">
            <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
              {t("collectionTypeLabel")}
            </p>

            <button
              type="button"
              className={`w-full text-left p-4 rounded-2xl border transition-all ${
                collectionType === "immediate"
                  ? "border-primary bg-primary/5"
                  : "border-border bg-background"
              }`}
              onClick={() => setCollectionType("immediate")}
            >
              <p className="font-semibold text-sm text-foreground">{t("collectionTypeImmediate")}</p>
              <p className="text-xs text-muted mt-1">{t("collectionTypeImmediateDesc")}</p>
            </button>

            <button
              type="button"
              className={`w-full text-left p-4 rounded-2xl border transition-all ${
                collectionType === "commit"
                  ? "border-primary bg-primary/5"
                  : "border-border bg-background"
              }`}
              onClick={() => setCollectionType("commit")}
            >
              <p className="font-semibold text-sm text-foreground">{t("collectionTypeCommit")}</p>
              <p className="text-xs text-muted mt-1">{t("collectionTypeCommitDesc")}</p>
            </button>

            <div className="border-t border-border mt-2 pt-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                  onClick={handleClose}
                >
                  {t("cancelButton")}
                </button>
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-40"
                  disabled={!collectionType}
                  onClick={() => setStep(2)}
                >
                  {t("next")}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {t("paymentMethodLabel")}
              </label>
              <input
                type="text"
                className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                maxLength={100}
                placeholder={t("paymentMethodPlaceholder")}
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.currentTarget.value)}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {t("paymentPhoneLabel")}
              </label>
              <input
                type="tel"
                className={`h-11 rounded-xl border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 ${phoneError ? "border-destructive" : "border-border"}`}
                placeholder={t("paymentPhonePlaceholder")}
                value={paymentPhone}
                onChange={(e) => { setPaymentPhone(e.currentTarget.value); setPhoneError(""); }}
                onBlur={handlePhoneBlur}
                required
              />
              {phoneError ? (
                <p className="text-xs text-destructive">{phoneError}</p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {t("paymentCommentLabel")}{" "}
                <span className="normal-case font-normal">{t("paymentCommentOptional")}</span>
              </label>
              <textarea
                className="min-h-16 max-h-24 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                maxLength={500}
                placeholder={t("paymentCommentPlaceholder")}
                value={paymentComment}
                onChange={(e) => setPaymentComment(e.currentTarget.value)}
              />
            </div>

            {submitError ? (
              <p className="text-xs text-destructive">{submitError}</p>
            ) : null}

            <div className="border-t border-border pt-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                  onClick={() => setStep(1)}
                  disabled={createMutation.isPending}
                >
                  {t("back")}
                </button>
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
                  disabled={createMutation.isPending || !paymentMethod.trim() || !paymentPhone.trim()}
                  onClick={handleSubmit}
                >
                  {createMutation.isPending ? t("creating") : t("createGiftButton")}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
