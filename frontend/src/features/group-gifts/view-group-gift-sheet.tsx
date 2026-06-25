"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n/useTranslation";
import { isPhoneMode, formatPhoneInput, validatePhoneOrCredentials } from "@/features/group-gifts/phone-utils";
import { useModalFocusMode } from "@/features/wishlists/use-modal-focus-mode";
import {
  useGroupGiftQuery,
  useCancelGroupGiftMutation,
  useJoinGroupGiftMutation,
  useReportTransferMutation,
  useLeaveGroupGiftMutation,
  useUpdateGroupGiftPaymentDetailsMutation,
  useMarkGroupGiftPurchasedMutation,
  useGiftMembersQuery,
} from "@/features/group-gifts/hooks";


type Props = {
  wishId: string;
  shareToken?: string | null;
  onClose: () => void;
};

type ContentProps = Props & {
  showTitle?: boolean;
  actionMode?: ActionMode;
  onActionModeChange?: (mode: ActionMode) => void;
  onFocusModeChange?: (isFocus: boolean) => void;
  resetTrigger?: number;
};

export type ActionMode = "overview" | "contribute" | "editPayment" | "purchase" | "cancel";

export function ViewGroupGiftSheet({ wishId, shareToken, onClose }: Props) {
  const [active, setActive] = useState(false);

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
        className={`modal-sheet ${active ? "visible" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <ViewGroupGiftContent wishId={wishId} shareToken={shareToken} onClose={handleClose} />
      </div>
    </div>
  );
}

export function ViewGroupGiftContent({ wishId, shareToken, onClose, showTitle = true, actionMode: controlledActionMode, onActionModeChange, onFocusModeChange, resetTrigger }: ContentProps) {
  const { t } = useTranslation();
  const focusMode = useModalFocusMode();

  const giftQuery = useGroupGiftQuery(wishId, shareToken);
  const gift = giftQuery.data ?? null;

  const cancelMutation = useCancelGroupGiftMutation(wishId, gift?.id ?? "");
  const updatePaymentMutation = useUpdateGroupGiftPaymentDetailsMutation(wishId, gift?.id ?? "");
  const purchaseMutation = useMarkGroupGiftPurchasedMutation(wishId, gift?.id ?? "");
  const joinMutation = useJoinGroupGiftMutation(wishId, gift?.id ?? "");
  const reportMutation = useReportTransferMutation(wishId, gift?.my_contribution?.id ?? "");
  const leaveMutation = useLeaveGroupGiftMutation(wishId, gift?.my_contribution?.id ?? "");
  const canLoadMembers = Boolean(gift && (gift.is_organizer || gift.is_contributor || gift.organizer_display_name));
  const membersQuery = useGiftMembersQuery(gift?.id, canLoadMembers);

  const [joinAmount, setJoinAmount] = useState("");
  const [leaveConfirming, setLeaveConfirming] = useState(false);
  const [phoneCopied, setPhoneCopied] = useState(false);
  const [internalActionMode, setInternalActionMode] = useState<ActionMode>("overview");
  const actionMode = controlledActionMode ?? internalActionMode;

  function changeActionMode(mode: ActionMode) {
    if (controlledActionMode === undefined) setInternalActionMode(mode);
    onActionModeChange?.(mode);
  }

  useEffect(() => {
    if (resetTrigger) changeActionMode("overview");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetTrigger]);

  useEffect(() => {
    onFocusModeChange?.(focusMode.isFocusMode);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusMode.isFocusMode]);

  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentPhone, setPaymentPhone] = useState("");
  const [paymentComment, setPaymentComment] = useState("");
  const [paymentPhoneError, setPaymentPhoneError] = useState("");

  const prevPercent = useRef(gift?.percent_complete ?? 0);
  const [percentOpacity, setPercentOpacity] = useState(1);

  useEffect(() => {
    if (!gift) return;
    if (gift.percent_complete !== prevPercent.current) {
      setPercentOpacity(0);
      const timer = window.setTimeout(() => setPercentOpacity(1), 50);
      prevPercent.current = gift.percent_complete;
      return () => window.clearTimeout(timer);
    }
  }, [gift?.percent_complete]);

  useEffect(() => {
    if (!gift || actionMode === "editPayment") return;
    setPaymentMethod(gift.payment_method ?? "");
    setPaymentPhone(gift.payment_phone ?? "");
    setPaymentComment(gift.payment_comment ?? "");
    setPaymentPhoneError("");
  }, [actionMode, gift]);

  function handleCopyPhone() {
    if (!gift?.payment_phone) return;
    navigator.clipboard.writeText(gift.payment_phone).then(() => {
      setPhoneCopied(true);
      window.setTimeout(() => setPhoneCopied(false), 2000);
    }).catch(() => {});
  }

  function handleCancelGift() {
    cancelMutation.mutate(undefined, { onSuccess: () => onClose() });
  }

  function handleSavePaymentDetails() {
    if (!gift) return;
    const trimmedMethod = paymentMethod.trim();
    const trimmedPhone = paymentPhone.trim();
    const trimmedComment = paymentComment.trim();
    if (!validatePhoneOrCredentials(trimmedPhone)) {
      setPaymentPhoneError(t("invalidPhoneNumber"));
      return;
    }
    updatePaymentMutation.mutate(
      {
        payment_method: trimmedMethod,
        payment_phone: trimmedPhone,
        payment_comment: trimmedComment || undefined,
      },
      {
        onSuccess: () => {
          changeActionMode("overview");
          setPaymentPhoneError("");
        },
      },
    );
  }

  function handleMarkPurchased() {
    purchaseMutation.mutate(undefined, {
      onSuccess: () => changeActionMode("overview"),
    });
  }

  function handleLeave() {
    if (!leaveConfirming) {
      setLeaveConfirming(true);
      return;
    }
    leaveMutation.mutate(undefined, { onSuccess: () => setLeaveConfirming(false) });
  }

  function handleJoin() {
    const amount = parseFloat(joinAmount);
    if (!amount || amount < 1) return;
    joinMutation.mutate(amount, {
      onSuccess: () => {
        setJoinAmount("");
        changeActionMode("overview");
      },
    });
  }

  return (
    <>
      {showTitle ? (
        <h3 className="modal-title font-bold text-base mb-4 text-center">{t("groupGift")}</h3>
      ) : null}

        {giftQuery.isPending ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
          </div>
        ) : !gift ? (
          <p className="text-sm text-muted text-center py-6">{t("giftNotActive")}</p>
        ) : actionMode !== "overview" ? (
          <div key={actionMode} className="action-mode-animate">
            {renderActionPanel()}
          </div>
        ) : (
          <div key="overview" className="action-mode-animate flex flex-col gap-4">
            <div className="flex flex-col gap-3">
              <div className="flex items-end justify-between gap-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("collected")}</span>
                  <span className="text-2xl font-bold text-foreground leading-none">{gift.collected_amount}</span>
                </div>
                {gift.total_amount ? (
                  <div className="flex flex-col gap-0.5 items-end">
                    <span className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("target")}</span>
                    <span className="text-lg font-semibold text-muted leading-none">{gift.total_amount}</span>
                  </div>
                ) : null}
              </div>

              <div className="w-full h-2.5 rounded-full bg-muted/20 overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
                  style={{ width: `${Math.min(100, gift.percent_complete)}%` }}
                />
              </div>

              <span
                className="text-xs text-muted transition-opacity duration-300 text-center"
                style={{ opacity: percentOpacity }}
              >
                {gift.percent_complete >= 100
                  ? t("giftComplete")
                  : t("giftProgress").replace("{percent}", String(gift.percent_complete))}
              </span>
            </div>

            <div className="border-t border-border pt-4">
              {renderActionPanel()}
            </div>

            {renderMembers()}
          </div>
        )}
    </>
  );

  function renderPaymentDetails() {
    if (!gift) return null;
    return (
      <div className="flex flex-col gap-1.5 bg-muted/5 rounded-xl p-3 border border-border">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {t("organizerRequisites")}
          </p>
          {gift.is_organizer ? (
            <button
              type="button"
              className="w-7 h-7 inline-flex items-center justify-center text-primary"
              onClick={() => changeActionMode("editPayment")}
              aria-label={t("editPaymentDetails")}
              title={t("editPaymentDetails")}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.25">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 7.125L16.875 4.5" />
              </svg>
            </button>
          ) : null}
        </div>
        {gift.payment_method ? (
          <p className="text-sm leading-tight text-foreground">{gift.payment_method}</p>
        ) : null}
        {gift.payment_phone ? (
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-tight font-semibold text-foreground">{gift.payment_phone}</p>
            <button
              type="button"
              className="text-xs font-semibold text-primary shrink-0"
              onClick={handleCopyPhone}
            >
              {phoneCopied ? t("phoneCopied") : t("copyPhone")}
            </button>
          </div>
        ) : null}
        {gift.payment_comment ? (
          <p className="text-xs leading-snug text-muted">{gift.payment_comment}</p>
        ) : null}
      </div>
    );
  }

  function renderPaymentDetailsForm() {
    const phoneMode = isPhoneMode(paymentPhone);
    return (
      <div className="flex flex-col gap-2.5">
        <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("method")}`}>
          <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {t("paymentMethodLabel")}
          </label>
          <input
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            maxLength={80}
            placeholder={t("paymentMethodPlaceholder")}
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.currentTarget.value.replace(/^\s+/, ""))}
            onBlur={focusMode.onFieldBlur}
            {...focusMode.fieldFocusProps("method")}
          />
        </div>

        <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("phone")}`}>
          <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {phoneMode ? t("paymentPhoneLabel") : t("credentialsOrPhoneLabel")}
          </label>
          <input
            inputMode={phoneMode ? "tel" : "text"}
            autoComplete="tel"
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder={t("credentialsOrPhonePlaceholder")}
            maxLength={phoneMode ? 20 : 50}
            value={paymentPhone}
            onBlur={() => {
              if (paymentPhone.trim()) {
                setPaymentPhoneError(validatePhoneOrCredentials(paymentPhone) ? "" : t("invalidPhoneNumber"));
              }
              focusMode.onFieldBlur();
            }}
            onChange={(e) => {
              const raw = e.currentTarget.value.replace(/^\s+/, "");
              setPaymentPhone(phoneMode || raw.startsWith("+") ? formatPhoneInput(raw) : raw);
              setPaymentPhoneError("");
            }}
            {...focusMode.fieldFocusProps("phone")}
          />
          {paymentPhoneError ? (
            <p className="text-xs text-red-500">{paymentPhoneError}</p>
          ) : null}
        </div>

        <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("comment")}`}>
          <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {t("paymentCommentLabel")}
          </label>
          <textarea
            className="min-h-16 rounded-xl border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
            maxLength={300}
            placeholder={t("paymentCommentPlaceholder")}
            value={paymentComment}
            onChange={(e) => setPaymentComment(e.currentTarget.value.replace(/^\s+/, ""))}
            onBlur={focusMode.onFieldBlur}
            {...focusMode.fieldFocusProps("comment")}
          />
        </div>

        <div className="modal-focus-footer flex gap-2">
          {focusMode.isFocusMode ? (
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-primary text-white text-sm font-bold"
              onClick={focusMode.clearFocus}
            >
              {t("done")}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="flex-1 h-10 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                onClick={() => {
                  changeActionMode("overview");
                  setPaymentMethod(gift?.payment_method ?? "");
                  setPaymentPhone(gift?.payment_phone ?? "");
                  setPaymentComment(gift?.payment_comment ?? "");
                  setPaymentPhoneError("");
                }}
              >
                {t("cancelButton")}
              </button>
              <button
                type="button"
                className="flex-1 h-10 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
                disabled={updatePaymentMutation.isPending || !paymentMethod.trim() || !paymentPhone.trim()}
                onClick={handleSavePaymentDetails}
              >
                {updatePaymentMutation.isPending ? t("saving") : t("savePaymentDetails")}
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  function renderMembers() {
    const members = membersQuery.data ?? [];
    if (!members.length) return null;
    // count includes organizer
    const total = members.length;
    return (
      <div className="flex flex-col gap-2 border-t border-border pt-3">
        <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
          {t("contributors")} ({total})
        </p>
        <div className="flex flex-col gap-1.5">
          {members.map((member) => {
            const displayName = member.first_name || (member.username ? `@${member.username}` : t("unknownUser"));
            const isOrganizer = member.role === "organizer";
            return (
              <div
                key={`${member.role}-${member.user_id}-${member.contribution_id ?? "creator"}`}
                className="flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {displayName}
                    {isOrganizer ? (
                      <span className="text-xs font-normal text-muted"> ({t("groupGiftCreator")})</span>
                    ) : null}
                  </p>
                  {member.username ? (
                    <button
                      type="button"
                      className="truncate text-xs text-muted pressable-link text-left"
                      onClick={() => {
                        navigator.clipboard.writeText(`@${member.username}`).catch(() => {});
                      }}
                    >
                      @{member.username}
                    </button>
                  ) : null}
                </div>
                {member.amount ? (
                  <p className="shrink-0 text-sm font-semibold text-foreground">{member.amount}</p>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderContributionForm() {
    return (
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {t("amountLabel")}
          </label>
          <input
            type="number"
            min={1}
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            placeholder={t("amountPlaceholder")}
            value={joinAmount}
            onChange={(e) => setJoinAmount(e.currentTarget.value)}
          />
        </div>
        <button
          type="button"
          className="w-full h-10 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
          disabled={joinMutation.isPending || !joinAmount || parseFloat(joinAmount) < 1}
          onClick={handleJoin}
        >
          {joinMutation.isPending ? t("saving") : t("confirmJoin")}
        </button>
      </div>
    );
  }

  function renderOrganizerActions() {
    return (
      <div className="flex flex-col gap-3">
        {!gift?.is_contributor ? (
          <button
            type="button"
            className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold"
            onClick={() => changeActionMode("contribute")}
          >
            {t("makeContribution")}
          </button>
        ) : null}
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            className="h-11 rounded-xl bg-muted/10 px-2 inline-flex items-center justify-center text-primary"
            onClick={() => changeActionMode("purchase")}
            aria-label={t("markGiftPurchased")}
            title={t("markGiftPurchased")}
          >
            <span className="min-w-0 truncate text-xs font-bold text-foreground">{t("actionPurchased")}</span>
          </button>
          <button
            type="button"
            className="h-11 rounded-xl bg-muted/10 px-2 inline-flex items-center justify-center text-primary"
            onClick={() => changeActionMode("editPayment")}
            aria-label={t("editPaymentDetails")}
            title={t("editPaymentDetails")}
          >
            <span className="min-w-0 truncate text-xs font-bold text-foreground">{t("actionEdit")}</span>
          </button>
          <button
            type="button"
            className="h-11 rounded-xl bg-red-500/10 px-2 inline-flex items-center justify-center text-red-500"
            onClick={() => changeActionMode("cancel")}
            aria-label={t("cancelGiftButton")}
            title={t("cancelGiftButton")}
          >
            <span className="min-w-0 truncate text-xs font-bold text-red-500">{t("actionCancel")}</span>
          </button>
        </div>
      </div>
    );
  }

  function renderActionState(children: ReactNode) {
    return (
      <div className="flex flex-col gap-3">
        {children}
      </div>
    );
  }

  function renderActionPanel() {
    if (!gift) return null;

    if (gift.status === "completed") {
      return (
        <p className="text-sm font-semibold text-muted text-center py-2">{t("giftComplete")}</p>
      );
    }
    if (gift.status === "cancelled") {
      return (
        <p className="text-sm font-semibold text-muted text-center py-2">{t("giftCancelled")}</p>
      );
    }

    if (actionMode === "contribute") {
      return renderActionState(renderContributionForm());
    }
    if (actionMode === "editPayment") {
      return renderActionState(renderPaymentDetailsForm());
    }
    if (actionMode === "purchase") {
      return renderActionState(
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted text-center">{t("confirmMarkGiftPurchased")}</p>
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-muted/10 text-muted text-sm font-medium"
              onClick={() => changeActionMode("overview")}
            >
              {t("cancelButton")}
            </button>
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
              disabled={purchaseMutation.isPending}
              onClick={handleMarkPurchased}
            >
              {purchaseMutation.isPending ? t("saving") : t("actionPurchased")}
            </button>
          </div>
        </div>,
      );
    }
    if (actionMode === "cancel") {
      return renderActionState(
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted text-center">{t("confirmCancelGift")}</p>
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-muted/10 text-muted text-sm font-medium"
              onClick={() => changeActionMode("overview")}
            >
              {t("cancelButton")}
            </button>
            <button
              type="button"
              className="theme-confirm-danger flex-1 h-10 rounded-xl text-sm font-bold disabled:opacity-60"
              disabled={cancelMutation.isPending}
              onClick={handleCancelGift}
            >
              {cancelMutation.isPending ? t("deleting") : t("actionCancel")}
            </button>
          </div>
        </div>,
      );
    }

    if (gift.is_organizer) {
      return renderOrganizerActions();
    }

    const contrib = gift.my_contribution;

    if (gift.is_contributor && contrib?.status === "waiting_transfer") {
      return (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted text-center">{t("waitingTransfer")}</p>
          {renderPaymentDetails()}

          <button
            type="button"
            className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
            disabled={reportMutation.isPending}
            onClick={() => reportMutation.mutate()}
          >
            {reportMutation.isPending ? t("saving") : t("iTransferred")}
          </button>

          {leaveConfirming ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted text-center">{t("confirmLeave")}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                  onClick={() => setLeaveConfirming(false)}
                >
                  {t("cancelButton")}
                </button>
                <button
                  type="button"
                  className="theme-confirm-danger flex-1 h-11 rounded-xl text-sm font-bold disabled:opacity-60"
                  disabled={leaveMutation.isPending}
                  onClick={handleLeave}
                >
                  {leaveMutation.isPending ? t("deleting") : t("leaveGiftButton")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="theme-press-danger w-full h-11 rounded-xl text-sm font-medium"
              onClick={() => setLeaveConfirming(true)}
            >
              {t("leaveGiftButton")}
            </button>
          )}
        </div>
      );
    }

    if (gift.is_contributor && contrib?.status === "waiting_confirmation") {
      return (
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="w-6 h-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
          <p className="text-sm text-muted text-center">{t("waitingConfirmation")}</p>
        </div>
      );
    }

    if (gift.is_contributor && contrib?.status === "confirmed") {
      return (
        <p className="text-sm font-semibold text-center" style={{ color: "var(--color-success, #22c55e)" }}>
          {t("transferConfirmedStatus")}
        </p>
      );
    }

    if (gift.is_contributor && contrib?.status === "pledged") {
      return (
        <div className="flex flex-col gap-3">
          {contrib.amount ? (
            <p className="text-sm text-muted text-center">
              {t("amountLabel")}: <span className="font-semibold text-foreground">{contrib.amount}</span>
            </p>
          ) : null}

          {leaveConfirming ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted text-center">{t("confirmLeave")}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                  onClick={() => setLeaveConfirming(false)}
                >
                  {t("cancelButton")}
                </button>
                <button
                  type="button"
                  className="theme-confirm-danger flex-1 h-11 rounded-xl text-sm font-bold disabled:opacity-60"
                  disabled={leaveMutation.isPending}
                  onClick={handleLeave}
                >
                  {leaveMutation.isPending ? t("deleting") : t("leaveGiftButton")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="theme-press-danger w-full h-11 rounded-xl text-sm font-medium"
              onClick={() => setLeaveConfirming(true)}
            >
              {t("leaveGiftButton")}
            </button>
          )}
        </div>
      );
    }

    if (gift.is_contributor && contrib?.status === "notified") {
      return (
        <div className="flex flex-col gap-3">
          {contrib.amount ? (
            <p className="text-sm text-muted text-center">
              {t("amountLabel")}: <span className="font-semibold text-foreground">{contrib.amount}</span>
            </p>
          ) : null}
          {renderPaymentDetails()}
        </div>
      );
    }

    if (!gift.is_organizer && !gift.is_contributor && gift.status === "active") {
      return (
        <button
          type="button"
          className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold"
          onClick={() => changeActionMode("contribute")}
        >
          {t("makeContribution")}
        </button>
      );
    }

    return null;
  }
}
