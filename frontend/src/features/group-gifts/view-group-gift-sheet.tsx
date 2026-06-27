"use client";

import type { ReactNode } from "react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

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
  useOrganizerRemoveContributionMutation,
  useToggleGroupGiftApprovalMutation,
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

export type ActionMode = "overview" | "contribute" | "editPayment" | "purchase" | "cancel" | "removeContribution" | "unbook" | "leave";

function stripTrailingZeros(amount: string): string {
  return amount.replace(/\.00$/, "");
}

function formatAmount(amount: string | null | undefined): string {
  if (!amount) return "";
  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return stripTrailingZeros(amount);
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numeric);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function getGiftProgress(collectedAmount: string | null | undefined, totalAmount: string | null | undefined): number {
  const collected = Number(collectedAmount);
  const target = Number(totalAmount);
  if (!Number.isFinite(collected) || !Number.isFinite(target) || target <= 0) return 0;
  return clamp(collected / target, 0, 1);
}

function interpolate(min: number, max: number, progress: number): number {
  return min + (max - min) * progress;
}

export function ViewGroupGiftSheet({ wishId, shareToken, onClose }: Props) {
  const [active, setActive] = useState(false);
  const [focusMode, setFocusMode] = useState(false);

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
        className={`modal-sheet ${active ? "visible" : ""} ${focusMode ? "keyboard-focus-mode" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <ViewGroupGiftContent wishId={wishId} shareToken={shareToken} onClose={handleClose} onFocusModeChange={setFocusMode} />
      </div>
    </div>
  );
}

export function ViewGroupGiftContent({
  wishId,
  shareToken,
  onClose,
  showTitle = true,
  actionMode: controlledActionMode,
  onActionModeChange,
  onFocusModeChange,
  resetTrigger,
}: ContentProps) {
  const { t } = useTranslation();
  const focusMode = useModalFocusMode();
  const isMounted = useRef(false);
  const giftWasLoaded = useRef(false);

  useEffect(() => {
    isMounted.current = true;
  }, []);

  const giftQuery = useGroupGiftQuery(wishId, shareToken);
  const gift = giftQuery.data ?? null;

  // Auto-close for all users when the gift is cancelled unanimously (polled null after being active)
  useEffect(() => {
    if (gift) { giftWasLoaded.current = true; return; }
    if (giftWasLoaded.current && giftQuery.data === null && !giftQuery.isPending) {
      onClose();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gift, giftQuery.isPending]);

  const cancelMutation = useCancelGroupGiftMutation(wishId, gift?.id ?? "");
  const approvalMutation = useToggleGroupGiftApprovalMutation(wishId, gift?.id ?? "");
  const updatePaymentMutation = useUpdateGroupGiftPaymentDetailsMutation(wishId, gift?.id ?? "");
  const purchaseMutation = useMarkGroupGiftPurchasedMutation(wishId, gift?.id ?? "");
  const joinMutation = useJoinGroupGiftMutation(wishId, gift?.id ?? "");
  const reportMutation = useReportTransferMutation(wishId, gift?.my_contribution?.id ?? "");
  const leaveMutation = useLeaveGroupGiftMutation(wishId, gift?.my_contribution?.id ?? "");
  const removeContribMutation = useOrganizerRemoveContributionMutation(wishId, gift?.id ?? "");
  const canLoadMembers = Boolean(gift && (gift.is_organizer || gift.is_contributor || gift.organizer_display_name));
  const membersQuery = useGiftMembersQuery(gift?.id, canLoadMembers);

  const [joinAmount, setJoinAmount] = useState("");
  const [phoneCopied, setPhoneCopied] = useState(false);
  const [internalActionMode, setInternalActionMode] = useState<ActionMode>("overview");
  const [removeContribution, setRemoveContribution] = useState<{
    id: string;
    isOrganizer: boolean;
    amount: string | null;
    displayName: string;
  } | null>(null);
  const [renderedActionMode, setRenderedActionMode] = useState<ActionMode>("overview");
  const overviewPanelRef = useRef<HTMLDivElement | null>(null);
  const actionPanelRef = useRef<HTMLDivElement | null>(null);
  const [overviewHeight, setOverviewHeight] = useState(0);
  const [actionHeight, setActionHeight] = useState(0);
  const actionMode = controlledActionMode ?? internalActionMode;
  const isNonOverview = actionMode !== "overview";
  const remainingAmount = gift?.remaining_amount ? Number(gift.remaining_amount) : null;
  const enteredContributionAmount = joinAmount ? Number(joinAmount) : 0;
  const remainingAfterContribution =
    remainingAmount !== null
      ? Math.max(0, remainingAmount - (Number.isFinite(enteredContributionAmount) ? enteredContributionAmount : 0))
      : null;
  const normalizedProgress = getGiftProgress(gift?.collected_amount, gift?.total_amount);
  const progressPercent = Math.round(normalizedProgress * 100);
  const collectedLabelScale = interpolate(0.88, 1.04, normalizedProgress);
  const collectedValueScale = interpolate(0.82, 1.08, normalizedProgress);
  const collectedWeight = Math.round(interpolate(600, 800, normalizedProgress));
  const collectedOpacity = interpolate(0.62, 1, normalizedProgress);
  const targetLabelScale = interpolate(1, 0.92, normalizedProgress);
  const targetValueScale = interpolate(1.15, 0.96, normalizedProgress);
  const targetWeight = Math.round(interpolate(760, 650, normalizedProgress));
  const targetOpacity = interpolate(1, 0.74, normalizedProgress);
  const isCollectedState = Boolean(
    gift?.status === "active" &&
    gift.total_amount &&
    (normalizedProgress >= 1 || remainingAmount === 0),
  );

  function changeActionMode(mode: ActionMode) {
    if (controlledActionMode === undefined) setInternalActionMode(mode);
    onActionModeChange?.(mode);
  }

  useEffect(() => {
    if (resetTrigger) changeActionMode("overview");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetTrigger]);

  useEffect(() => {
    if (actionMode !== "overview") {
      setRenderedActionMode(actionMode);
      return undefined;
    }

    const timer = window.setTimeout(() => setRenderedActionMode("overview"), 280);
    return () => window.clearTimeout(timer);
  }, [actionMode]);

  useLayoutEffect(() => {
    const updateHeights = () => {
      setOverviewHeight(overviewPanelRef.current?.scrollHeight ?? 0);
      setActionHeight(actionPanelRef.current?.scrollHeight ?? 0);
    };

    updateHeights();

    if (typeof ResizeObserver === "undefined") {
      return undefined;
    }

    const observer = new ResizeObserver(updateHeights);
    if (overviewPanelRef.current) observer.observe(overviewPanelRef.current);
    if (actionPanelRef.current) observer.observe(actionPanelRef.current);

    return () => observer.disconnect();
  });

  useEffect(() => {
    if (!gift?.is_contributor) {
      setJoinAmount("");
    }
  }, [gift?.is_contributor]);

  useEffect(() => {
    onFocusModeChange?.(focusMode.isFocusMode);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusMode.isFocusMode]);

  const [paymentMethod, setPaymentMethod] = useState("");
  const [paymentPhone, setPaymentPhone] = useState("");
  const [paymentComment, setPaymentComment] = useState("");
  const [paymentPhoneError, setPaymentPhoneError] = useState("");

  useEffect(() => {
    if (!gift || actionMode === "editPayment") return;
    setPaymentMethod(gift.payment_method ?? "");
    setPaymentPhone(gift.payment_phone ?? "");
    setPaymentComment(gift.payment_comment ?? "");
    setPaymentPhoneError("");
  }, [actionMode, gift]);

  // Title shown inside the sheet when used standalone (showTitle=true)
  function getActionTitle(): string {
    if (actionMode === "contribute") return t("makeContribution");
    if (actionMode === "editPayment") return t("editPaymentDetails");
    if (actionMode === "purchase") return t("groupGift");
    if (actionMode === "cancel") return t("groupGift");
    if (actionMode === "unbook") return t("groupGift");
    if (actionMode === "leave") return "";
    if (actionMode === "removeContribution") return t("removeContribution");
    return t("groupGift");
  }

  function handleCopyPhone() {
    if (!gift?.payment_phone) return;
    navigator.clipboard.writeText(gift.payment_phone).then(() => {
      setPhoneCopied(true);
      window.setTimeout(() => setPhoneCopied(false), 2000);
    }).catch(() => {});
  }

  function handleCancelGift() {
    approvalMutation.mutate("cancel", {
      onSuccess: (result) => {
        if (result === null) onClose();
        else changeActionMode("overview");
      },
    });
  }

  function handleUnbookApproval() {
    approvalMutation.mutate("unbook", {
      onSuccess: () => changeActionMode("overview"),
    });
  }

  function handleSavePaymentDetails() {
    if (!gift) return;
    const trimmedMethod = paymentMethod.trim();
    const trimmedPhone = paymentPhone.trim();
    const trimmedComment = paymentComment.trim();
    if (trimmedPhone && !validatePhoneOrCredentials(trimmedPhone)) {
      setPaymentPhoneError(t("invalidPhoneNumber"));
      return;
    }
    updatePaymentMutation.mutate(
      { payment_method: trimmedMethod, payment_phone: trimmedPhone || null, payment_comment: trimmedComment || undefined },
      {
        onSuccess: () => {
          changeActionMode("overview");
          setPaymentPhoneError("");
        },
      },
    );
  }

  function handleMarkPurchased() {
    purchaseMutation.mutate(undefined, { onSuccess: () => changeActionMode("overview") });
  }

  function handleLeave() {
    leaveMutation.mutate(undefined, { onSuccess: () => changeActionMode("overview") });
  }

  function handleLeaveImmediately() {
    leaveMutation.mutate(undefined, { onSuccess: () => changeActionMode("overview") });
  }

  function handleJoin() {
    const amount = parseFloat(joinAmount);
    if (!amount || amount < 1) return;
    if (remainingAmount !== null && amount > remainingAmount) return;
    joinMutation.mutate(amount, {
      onSuccess: () => { setJoinAmount(""); changeActionMode("overview"); },
    });
  }

  function handleRemoveContribution() {
    if (!removeContribution) return;
    const onSuccess = () => {
      setRemoveContribution(null);
      changeActionMode("overview");
    };
    if (removeContribution.isOrganizer) {
      leaveMutation.mutate(undefined, { onSuccess });
      return;
    }
    removeContribMutation.mutate(removeContribution.id, { onSuccess });
  }

  const overviewPanel = renderOverviewPanel();

  return (
    <>
      {showTitle && getActionTitle() ? (
        <h3 className={`modal-title font-bold text-base mb-4 text-center ${focusMode.sectionClass("titleText")}`}>{getActionTitle()}</h3>
      ) : null}

      {giftQuery.isPending ? (
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
        </div>
      ) : !gift || cancelMutation.isSuccess ? (
        cancelMutation.isSuccess ? null : (
          <p className="text-sm text-muted text-center py-6">{t("giftNotActive")}</p>
        )
      ) : (
        <div className="flex flex-col">
          <div
            className={`modal-footer-transition ${
              !isNonOverview
                ? "opacity-100 scale-100"
                : "opacity-0 scale-95 pointer-events-none overflow-hidden"
            }`}
            style={{ maxHeight: !isNonOverview ? (isMounted.current ? overviewHeight : undefined) : 0 }}
          >
            <div ref={overviewPanelRef} className="flex flex-col gap-4">
              <div className="flex flex-col gap-3">
                <div className="flex items-end justify-between gap-3">
                  <div className="flex min-h-12 flex-col justify-end gap-0.5">
                    <span
                      className="origin-bottom-left text-[10px] font-extrabold text-muted uppercase tracking-wider transition-[transform,opacity] duration-300 ease-out will-change-transform"
                      style={{ transform: `scale(${collectedLabelScale})`, opacity: collectedOpacity }}
                    >
                      {t("collected")}
                    </span>
                    <span
                      className="origin-bottom-left text-2xl text-foreground leading-none transition-[transform,font-weight,opacity] duration-300 ease-out will-change-transform"
                      style={{
                        transform: `scale(${collectedValueScale})`,
                        fontWeight: collectedWeight,
                        opacity: collectedOpacity,
                      }}
                    >
                      {formatAmount(gift.collected_amount)}
                    </span>
                  </div>
                  {gift.total_amount ? (
                    <div className="flex min-h-12 flex-col items-end justify-end gap-0.5">
                      <span
                        className="origin-bottom-right text-[10px] font-extrabold text-muted uppercase tracking-wider transition-[transform,opacity] duration-300 ease-out will-change-transform"
                        style={{ transform: `scale(${targetLabelScale})`, opacity: targetOpacity }}
                      >
                        {t("target")}
                      </span>
                      <span
                        className="origin-bottom-right text-2xl text-muted leading-none transition-[transform,font-weight,opacity] duration-300 ease-out will-change-transform"
                        style={{
                          transform: `scale(${targetValueScale})`,
                          fontWeight: targetWeight,
                          opacity: targetOpacity,
                        }}
                      >
                        {formatAmount(gift.total_amount)}
                      </span>
                    </div>
                  ) : null}
                </div>

                <div className="w-full h-2.5 rounded-full bg-muted/20 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <span
                  className="text-xs text-muted transition-opacity duration-300 text-center"
                >
                  {isCollectedState
                    ? t("collectedState")
                    : normalizedProgress >= 1
                    ? t("giftComplete")
                    : t("giftProgress").replace("{percent}", String(progressPercent))}
                </span>
              </div>

              {overviewPanel ? (
                <div className="border-t border-border pt-4">
                  {overviewPanel}
                </div>
              ) : null}

              {renderMembers()}
              {renderCancelButton()}
            </div>
          </div>

          <div
            className={`modal-footer-transition ${
              isNonOverview
                ? "opacity-100 scale-100"
                : "opacity-0 scale-95 pointer-events-none overflow-hidden"
            }`}
            style={{ maxHeight: isNonOverview ? actionHeight : 0 }}
          >
            <div ref={actionPanelRef}>{renderNonOverviewPanel()}</div>
          </div>
        </div>
      )}
    </>
  );

  // ── Overview panel: organizer actions / contributor statuses (shown only in overview section) ──

  function renderOverviewPanel(): ReactNode {
    if (!gift) return null;
    if (gift.status === "completed") {
      const canUnbook = gift.is_organizer || gift.is_contributor;
      return (
        <div className="flex flex-col gap-3">
          <p className="text-sm font-semibold text-muted text-center py-2">{t("giftComplete")}</p>
          {canUnbook ? (
            <button
              type="button"
              className={`w-full h-11 rounded-xl text-sm font-bold transition-colors ${
                gift.my_unbook_approval
                  ? "bg-primary text-white"
                  : "bg-muted/10 text-foreground"
              }`}
              disabled={approvalMutation.isPending}
              onClick={() => changeActionMode("unbook")}
            >
              {t("unbookApproval")}
              {gift.participant_count > 1 ? (
                <span className="ml-2 text-xs font-normal opacity-70">
                  {t("approvedOf")
                    .replace("{approved}", String(gift.unbook_approval_count))
                    .replace("{total}", String(gift.participant_count))}
                </span>
              ) : null}
            </button>
          ) : null}
        </div>
      );
    }
    if (gift.status === "cancelled") {
      return <p className="text-sm font-semibold text-muted text-center py-2">{t("giftCancelled")}</p>;
    }
    if (gift.is_organizer) return renderOrganizerActions();
    const contrib = gift.my_contribution;
    if (isCollectedState && gift.is_contributor && contrib) {
      return (
        <div className="flex flex-col gap-3">
          {gift.organizer_display_name ? (
            <p className="text-xs text-muted text-center">
              {t("groupGiftCreator")}: <span className="font-semibold text-foreground">{gift.organizer_display_name}</span>
            </p>
          ) : null}
          <p className="text-sm font-semibold text-center" style={{ color: "var(--color-success, #22c55e)" }}>
            {contrib.status === "waiting_transfer"
              ? t("waitingTransfer")
              : contrib.status === "waiting_confirmation"
              ? t("waitingConfirmation")
              : t("transferConfirmedStatus")}
          </p>
          {contrib.status !== "waiting_transfer" && contrib.status !== "waiting_confirmation" ? (
            <p className="text-[11px] leading-snug text-muted text-center -mt-1">
              {t("transferConfirmedHint")}
            </p>
          ) : null}
          {renderPaymentDetails({ showEdit: false, compact: true })}
        </div>
      );
    }
    if (gift.is_contributor && contrib?.status === "waiting_transfer") {
      return (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted text-center">{t("waitingTransfer")}</p>
          {renderPaymentDetails({ showEdit: false, compact: true })}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="w-10 h-11 inline-flex items-center justify-center rounded-xl text-muted hover:text-red-500 transition-colors disabled:opacity-50"
              disabled={leaveMutation.isPending}
              onClick={handleLeaveImmediately}
              aria-label={t("leaveGiftButton")}
              title={t("leaveGiftButton")}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
              </svg>
            </button>
            <button
              type="button"
              className="flex-1 h-11 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
              disabled={reportMutation.isPending || leaveMutation.isPending}
              onClick={() => reportMutation.mutate()}
            >
              {reportMutation.isPending ? t("saving") : t("iTransferred")}
            </button>
          </div>
        </div>
      );
    }
    if (gift.is_contributor && contrib?.status === "waiting_confirmation") {
      return (
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="w-8 h-8 rounded-full border-[3px] border-primary/20 border-t-primary animate-spin" />
          <p className="text-sm text-muted text-center">{t("waitingConfirmation")}</p>
          <button
            type="button"
            className="w-8 h-8 inline-flex items-center justify-center rounded-full text-muted hover:text-red-500 transition-colors disabled:opacity-50"
            disabled={leaveMutation.isPending}
            onClick={handleLeaveImmediately}
            aria-label={t("leaveGiftButton")}
            title={t("leaveGiftButton")}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
            </svg>
          </button>
        </div>
      );
    }
    if (gift.is_contributor && contrib?.status === "confirmed") {
      return (
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold text-center" style={{ color: "var(--color-success, #22c55e)" }}>
            {t("transferConfirmedStatus")}
          </p>
          <p className="text-[11px] leading-snug text-muted text-center">
            {t("transferConfirmedHint")}
          </p>
        </div>
      );
    }
    if (gift.is_contributor && contrib?.status === "pledged") {
      return (
        <div className="flex flex-col gap-3">
          {renderCancelApprovalToggle()}
        </div>
      );
    }
    if (gift.is_contributor && contrib?.status === "notified") {
      return (
        <div className="flex flex-col gap-3">
          {contrib.amount ? (
            <p className="text-sm text-muted text-center">
              {t("amountLabel")}: <span className="font-semibold text-foreground">{formatAmount(contrib.amount)}</span>
            </p>
          ) : null}
          {renderPaymentDetails({ showEdit: false, compact: true })}
        </div>
      );
    }
    if (!gift.is_organizer && !gift.is_contributor && gift.status === "active" && !isCollectedState) {
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

  function renderCancelApprovalToggle(): ReactNode {
    return null;
  }

  function renderCancelButton(): ReactNode {
    if (!gift || gift.status !== "active") return null;
    if (!gift.is_contributor || gift.is_organizer) return null;
    const myApproval = gift.my_cancel_approval ?? false;
    return (
      <div className="pt-2">
        <button
          type="button"
          className={`w-full h-10 rounded-xl text-sm font-medium transition-colors ${
            myApproval
              ? "bg-red-500/20 text-red-600"
              : "bg-muted/10 text-muted"
          }`}
          disabled={approvalMutation.isPending}
          onClick={() => changeActionMode("cancel")}
        >
          {myApproval ? t("undoCancelApproval") : t("actionCancel")}
          {(gift.participant_count ?? 0) > 1 ? (
            <span className="ml-2 text-xs opacity-70">
              {gift.cancel_approval_count}/{gift.participant_count}
            </span>
          ) : null}
        </button>
      </div>
    );
  }

  // ── Non-overview panel: forms/confirmations (shown only in action section) ──

  function renderNonOverviewPanel(): ReactNode {
    if (!gift) return null;
    const mode = isNonOverview ? actionMode : renderedActionMode;
    if (mode === "contribute") {
      return (
        <div className="flex flex-col gap-2.5">
          {renderPaymentDetails({ showEdit: false, compact: true })}
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
              {t("amountLabel")}
            </label>
            <input
              type="number"
              min={1}
              max={remainingAmount ?? undefined}
              className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder={t("amountPlaceholder")}
              value={joinAmount}
              onChange={(e) => setJoinAmount(e.currentTarget.value)}
            />
            {remainingAmount !== null ? (
              <p className="text-xs text-muted">
                {t("remainingAmount").replace("{amount}", formatAmount(String(remainingAfterContribution)))}
              </p>
            ) : null}
          </div>
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
              disabled={
                joinMutation.isPending ||
                !joinAmount ||
                parseFloat(joinAmount) < 1 ||
                (remainingAmount !== null && parseFloat(joinAmount) > remainingAmount)
              }
              onClick={handleJoin}
            >
              {joinMutation.isPending ? t("saving") : t("confirmJoin")}
            </button>
          </div>
        </div>
      );
    }
    if (mode === "editPayment") {
      return renderPaymentDetailsForm();
    }
    if (mode === "purchase") {
      return (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted text-center leading-relaxed">
            {t("confirmMarkGiftPurchased")}
          </p>
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
              className="flex-1 h-10 rounded-xl bg-green-500 text-white text-sm font-bold disabled:opacity-60"
              disabled={purchaseMutation.isPending}
              onClick={handleMarkPurchased}
            >
              {purchaseMutation.isPending ? t("saving") : t("actionPurchased")}
            </button>
          </div>
        </div>
      );
    }
    if (mode === "cancel") {
      const cancelCount = gift.cancel_approval_count ?? 0;
      const participantCount = gift.participant_count ?? 1;
      const myApproval = gift.my_cancel_approval ?? false;
      return (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted text-center">
            {myApproval ? t("undoCancelApprovalInfo") : t("groupGiftCancelInfo")}
          </p>
          {participantCount > 1 ? (
            <p className="text-xs font-semibold text-center text-foreground">
              {t("approvedOf")
                .replace("{approved}", String(cancelCount))
                .replace("{total}", String(participantCount))}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-muted/10 text-muted text-sm font-medium"
              onClick={() => changeActionMode("overview")}
            >
              {t("back")}
            </button>
            <button
              type="button"
              className={`flex-1 h-10 rounded-xl text-sm font-bold disabled:opacity-60 ${
                myApproval ? "bg-primary text-white" : "theme-confirm-danger"
              }`}
              disabled={approvalMutation.isPending}
              onClick={handleCancelGift}
            >
              {approvalMutation.isPending
                ? t("saving")
                : myApproval
                ? t("undoButton")
                : t("doButton")}
            </button>
          </div>
        </div>
      );
    }
    if (mode === "unbook") {
      const unbookCount = gift.unbook_approval_count ?? 0;
      const participantCount = gift.participant_count ?? 1;
      const myApproval = gift.my_unbook_approval ?? false;
      return (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted text-center">{t("groupGiftUnbookInfo")}</p>
          {participantCount > 1 ? (
            <p className="text-xs font-semibold text-center text-foreground">
              {t("approvedOf")
                .replace("{approved}", String(unbookCount))
                .replace("{total}", String(participantCount))}
            </p>
          ) : null}
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
              className={`flex-1 h-10 rounded-xl text-sm font-bold disabled:opacity-60 ${
                myApproval ? "bg-primary text-white" : "bg-muted/20 text-foreground"
              }`}
              disabled={approvalMutation.isPending}
              onClick={handleUnbookApproval}
            >
              {approvalMutation.isPending
                ? t("saving")
                : myApproval
                ? t("cancelButton")
                : t("unbookApproval")}
            </button>
          </div>
        </div>
      );
    }
    if (mode === "leave") {
      return (
        <div className="flex flex-col gap-1.5 pt-0">
          <p className="text-xs text-muted text-center leading-snug">{t("confirmLeave")}</p>
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
              disabled={leaveMutation.isPending}
              onClick={handleLeave}
            >
              {leaveMutation.isPending ? t("deleting") : t("leaveGiftButton")}
            </button>
          </div>
        </div>
      );
    }
    if (mode === "removeContribution") {
      return (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-1 text-center">
            <p className="text-xs text-muted">{removeContribution?.displayName ?? t("unknownUser")}</p>
            {removeContribution?.amount ? (
              <p className="text-sm font-semibold text-foreground">{formatAmount(removeContribution.amount)}</p>
            ) : null}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 h-10 rounded-xl bg-muted/10 text-muted text-sm font-medium"
              onClick={() => {
                changeActionMode("overview");
                window.setTimeout(() => setRemoveContribution(null), 280);
              }}
            >
              {t("cancelButton")}
            </button>
            <button
              type="button"
              className="theme-confirm-danger flex-1 h-10 rounded-xl text-sm font-bold disabled:opacity-60"
              disabled={removeContribution?.isOrganizer ? leaveMutation.isPending : removeContribMutation.isPending}
              onClick={handleRemoveContribution}
            >
              {(removeContribution?.isOrganizer ? leaveMutation.isPending : removeContribMutation.isPending)
                ? t("deleting")
                : t("removeButton")}
            </button>
          </div>
        </div>
      );
    }
    return null;
  }

  // ── Shared sub-renders ──

  function renderPaymentDetails(options: { showEdit?: boolean; compact?: boolean } = {}) {
    if (!gift) return null;
    const showEdit = options.showEdit ?? gift.is_organizer;
    return (
      <div className={options.compact ? "flex flex-col gap-1.5 rounded-xl bg-muted/5 px-3 py-2.5" : "flex flex-col gap-2 rounded-xl border border-border/80 bg-background px-3 py-2.5 shadow-sm"}>
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
            {t("organizerRequisites")}
          </p>
          {showEdit ? (
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
          <p className="text-sm leading-tight font-semibold text-foreground">{gift.payment_method}</p>
        ) : null}
        {gift.payment_phone ? (
          <button
            type="button"
            className={options.compact ? "w-full text-left text-sm font-semibold leading-tight text-foreground transition-opacity hover:opacity-80" : "w-full text-left rounded-lg bg-muted/5 px-3 py-2 transition-colors hover:bg-muted/10"}
            onClick={handleCopyPhone}
          >
            {options.compact ? (
              <span>{phoneCopied ? t("phoneCopied") : gift.payment_phone}</span>
            ) : (
              <>
                <span className="block text-[10px] font-bold uppercase tracking-wider text-muted">
                  {phoneCopied ? t("phoneCopied") : t("copyPhone")}
                </span>
                <span className="block text-sm font-semibold leading-tight text-foreground">{gift.payment_phone}</span>
              </>
            )}
          </button>
        ) : null}
        {gift.payment_comment ? (
          <p className={options.compact ? "text-xs leading-snug text-muted" : "rounded-lg bg-muted/5 px-3 py-2 text-xs leading-snug text-muted"}>{gift.payment_comment}</p>
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
              const raw = e.currentTarget.value.replace(/[^0-9+\s\-()]/g, "");
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
        <div className="modal-focus-footer border-t border-border pt-3 flex gap-2">
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
                disabled={updatePaymentMutation.isPending || !paymentMethod.trim()}
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

  function renderOrganizerActions() {
    if (isCollectedState) {
      return (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className="w-full h-11 rounded-xl bg-green-500 text-white text-sm font-bold"
            onClick={() => changeActionMode("purchase")}
          >
            {t("actionPurchased")}
          </button>
        </div>
      );
    }

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
            className="h-11 rounded-xl bg-green-500/10 px-2 inline-flex items-center justify-center"
            onClick={() => changeActionMode("purchase")}
          >
            <span className="min-w-0 truncate text-xs font-bold text-green-600">{t("actionPurchased")}</span>
          </button>
          <button
            type="button"
            className="h-11 rounded-xl bg-muted/10 px-2 inline-flex items-center justify-center"
            onClick={() => changeActionMode("editPayment")}
          >
            <span className="min-w-0 truncate text-xs font-bold text-foreground">{t("actionEdit")}</span>
          </button>
          <button
            type="button"
            className={`h-11 rounded-xl px-2 inline-flex flex-col items-center justify-center gap-0.5 ${
              gift?.my_cancel_approval ? "bg-red-500/20" : "bg-red-500/10"
            }`}
            onClick={() => {
              if ((gift?.participant_count ?? 0) <= 1) {
                handleCancelGift();
              } else {
                changeActionMode("cancel");
              }
            }}
          >
            <span className="min-w-0 truncate text-xs font-bold text-red-500">{t("actionCancel")}</span>
            {(gift?.participant_count ?? 0) > 1 ? (
              <span className="text-[9px] text-red-400">
                {gift?.cancel_approval_count}/{gift?.participant_count}
              </span>
            ) : null}
          </button>
        </div>
      </div>
    );
  }

  function renderMembers() {
    if (!canLoadMembers) return null;
    const members = membersQuery.data ?? [];
    if (!members.length) return null;

    const organizerMember = members.find((m) => m.role === "organizer");
    const organizerContribAsContributor = organizerMember
      ? members.find((m) => m.role === "contributor" && m.user_id === organizerMember.user_id)
      : null;

    const filteredMembers = members.filter(
      (m) => !(m.role === "contributor" && m.user_id === organizerMember?.user_id),
    );

    return (
      <div className="flex flex-col gap-2 border-t border-border pt-3">
        <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
          {t("contributors")} ({filteredMembers.length})
        </p>
        <div className="flex flex-col gap-1.5">
          {filteredMembers.map((member) => {
            const displayName = member.first_name || (member.username ? `@${member.username}` : t("unknownUser"));
            const isOrganizer = member.role === "organizer";
            const displayAmount = isOrganizer && organizerContribAsContributor?.amount
              ? organizerContribAsContributor.amount
              : member.amount;
            const contributionId = isOrganizer
              ? organizerContribAsContributor?.contribution_id
              : member.contribution_id;
            const isMyContribution = Boolean(
              gift?.my_contribution?.id && contributionId === gift.my_contribution.id,
            );
            const canRemoveContribution = Boolean(
              contributionId && (
                gift?.is_organizer ||
                (isMyContribution && !["confirmed", "notified"].includes(member.status ?? ""))
              ),
            );
            return (
              <div key={`${member.role}-${member.user_id}-${member.contribution_id ?? "creator"}`}>
                <div className="flex items-center justify-between gap-3">
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
                        onClick={() => navigator.clipboard.writeText(`@${member.username}`).catch(() => {})}
                      >
                        @{member.username}
                      </button>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 justify-end">
                    {displayAmount ? (
                      <p className="min-w-[2.5rem] text-right text-sm font-semibold text-foreground">
                        {formatAmount(displayAmount)}
                      </p>
                    ) : null}
                    {canRemoveContribution ? (
                      <button
                        type="button"
                        className="w-6 h-6 inline-flex items-center justify-center rounded-full text-muted hover:text-red-500 transition-colors"
                        onClick={() => {
                          if (!contributionId) return;
                          setRemoveContribution({
                            id: contributionId,
                            isOrganizer,
                            amount: displayAmount ?? null,
                            displayName,
                          });
                          changeActionMode("removeContribution");
                        }}
                        aria-label={t("removeContribution")}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
}
