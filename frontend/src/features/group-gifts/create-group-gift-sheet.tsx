"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/api-client";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { useCreateGroupGiftMutation } from "@/features/group-gifts/hooks";
import type { GroupGiftCreatePayload } from "@/features/group-gifts/api";
import { isPhoneMode, formatPhoneInput, formatAccountInput, validatePhoneOrCredentials } from "@/features/group-gifts/phone-utils";
import { useModalFocusMode } from "@/features/wishlists/use-modal-focus-mode";

type Props = {
  wishId: string;
  shareToken?: string | null;
  onClose: () => void;
};

type CreateGroupGiftContentProps = {
  wishId: string;
  onClose: () => void;
  onCancel?: () => void;
  showTitle?: boolean;
  onFocusModeChange?: (isFocus: boolean) => void;
};

const ERROR_MAP: Record<string, string> = {
  group_gift_already_exists: "giftAlreadyExists",
  gift_not_active: "giftNotActive",
};

export function CreateGroupGiftSheet({ wishId, onClose }: Props) {
  const [active, setActive] = useState(false);
  const [focusModeActive, setFocusModeActive] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet ${active ? "visible" : ""} ${focusModeActive ? "keyboard-focus-mode" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <CreateGroupGiftContent wishId={wishId} onClose={handleClose} onFocusModeChange={setFocusModeActive} />
      </div>
    </div>
  );
}

export function CreateGroupGiftContent({
  wishId,
  onClose,
  onCancel,
  showTitle = true,
  onFocusModeChange,
}: CreateGroupGiftContentProps) {
  const { t } = useTranslation();
  const focusMode = useModalFocusMode();
  const [step, setStep] = useState<1 | 2>(1);
  const [collectionType, setCollectionType] = useState<"immediate" | "commit" | null>(null);
  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentPhone, setPaymentPhone] = useState("");
  const [paymentComment, setPaymentComment] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [submitError, setSubmitError] = useState("");

  const createMutation = useCreateGroupGiftMutation(wishId);

  useEffect(() => {
    onFocusModeChange?.(focusMode.isFocusMode);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusMode.isFocusMode]);

  function handlePhoneBlur() {
    if (paymentPhone.trim() && !validatePhoneOrCredentials(paymentPhone)) {
      setPhoneError(t("invalidPhoneNumber"));
    } else {
      setPhoneError("");
    }
  }

  function handleSubmit() {
    if (!collectionType) return;
    if (paymentPhone.trim() && !validatePhoneOrCredentials(paymentPhone)) {
      setPhoneError(t("invalidPhoneNumber"));
      return;
    }
    setPhoneError("");

    const payload: GroupGiftCreatePayload = {
      collection_type: collectionType,
      payment_method: paymentMethod.trim(),
      payment_phone: paymentPhone.trim() || null,
      ...(paymentComment.trim() ? { payment_comment: paymentComment.trim() } : {}),
    };

    setSubmitError("");
    createMutation.mutate(payload, {
      onSuccess: () => onClose(),
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
    <>
      {showTitle ? (
        <h3 className={`modal-title font-bold text-base mb-4 text-center ${focusMode.sectionClass("titleText")}`}>
          {t("createGroupGift")}
        </h3>
      ) : null}

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
                  onClick={onCancel ?? onClose}
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
            <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("method")}`}>
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {t("paymentMethodLabel")}
              </label>
              <input
                type="text"
                className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                maxLength={80}
                placeholder={t("paymentMethodPlaceholder")}
                value={paymentMethod}
                onChange={(e) => setPaymentMethod(e.currentTarget.value.replace(/^\s+/, ""))}
                onBlur={focusMode.onFieldBlur}
                required
                {...focusMode.fieldFocusProps("method")}
              />
            </div>

            <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("phone")}`}>
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {!paymentPhone.trim() ? t("credentialsOrPhoneLabel") : (isPhoneMode(paymentPhone) ? t("paymentPhoneLabel") : t("paymentAccountLabel"))}
              </label>
              <input
                inputMode={isPhoneMode(paymentPhone) ? "tel" : "text"}
                autoComplete="tel"
                className={`h-11 rounded-xl border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 ${phoneError ? "border-destructive" : "border-border"}`}
                placeholder={t("credentialsOrPhonePlaceholder")}
                maxLength={isPhoneMode(paymentPhone) ? 20 : 50}
                value={paymentPhone}
                onChange={(e) => {
                  const raw = e.currentTarget.value.replace(/[^0-9+\s\-()]/g, "");
                  if (raw.startsWith("+")) {
                    setPaymentPhone(formatPhoneInput(raw));
                  } else {
                    setPaymentPhone(raw ? formatAccountInput(raw) : "");
                  }
                  setPhoneError("");
                }}
                onBlur={() => { handlePhoneBlur(); focusMode.onFieldBlur(); }}
                {...focusMode.fieldFocusProps("phone")}
              />
              {phoneError ? (
                <p className="text-xs text-destructive">{phoneError}</p>
              ) : null}
            </div>

            <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("comment")}`}>
              <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
                {t("paymentCommentLabel")}
              </label>
              <textarea
                className="min-h-16 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                maxLength={300}
                placeholder={t("paymentCommentPlaceholder")}
                value={paymentComment}
                onChange={(e) => setPaymentComment(e.currentTarget.value.replace(/^\s+/, ""))}
                onBlur={focusMode.onFieldBlur}
                {...focusMode.fieldFocusProps("comment")}
              />
            </div>

            {submitError ? (
              <p className="text-xs text-destructive">{submitError}</p>
            ) : null}

            <div className="modal-focus-footer border-t border-border pt-3">
              {focusMode.isFocusMode ? (
                <button
                  type="button"
                  className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold"
                  onClick={focusMode.clearFocus}
                >
                  {t("done")}
                </button>
              ) : (
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
                    disabled={createMutation.isPending || !paymentMethod.trim()}
                    onClick={handleSubmit}
                  >
                    {createMutation.isPending ? t("creating") : t("createGiftButton")}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
    </>
  );
}
