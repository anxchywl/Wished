"use client";

import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n/useTranslation";
import {
  useGroupGiftQuery,
  useCancelGroupGiftMutation,
  useJoinGroupGiftMutation,
  useReportTransferMutation,
  useLeaveGroupGiftMutation,
} from "@/features/group-gifts/hooks";

type Props = {
  wishId: string;
  shareToken?: string | null;
  onClose: () => void;
};

export function ViewGroupGiftSheet({ wishId, shareToken, onClose }: Props) {
  const { t } = useTranslation();
  const [active, setActive] = useState(false);

  const giftQuery = useGroupGiftQuery(wishId, shareToken);
  const gift = giftQuery.data ?? null;

  const cancelMutation = useCancelGroupGiftMutation(wishId, gift?.id ?? "");
  const joinMutation = useJoinGroupGiftMutation(wishId, gift?.id ?? "");
  const reportMutation = useReportTransferMutation(wishId, gift?.my_contribution?.id ?? "");
  const leaveMutation = useLeaveGroupGiftMutation(wishId, gift?.my_contribution?.id ?? "");

  const [joinAmount, setJoinAmount] = useState("");
  const [leaveConfirming, setLeaveConfirming] = useState(false);
  const [cancelConfirming, setCancelConfirming] = useState(false);
  const [phoneCopied, setPhoneCopied] = useState(false);

  const prevPercent = useRef(gift?.percent_complete ?? 0);
  const [percentOpacity, setPercentOpacity] = useState(1);

  useEffect(() => {
    requestAnimationFrame(() => setActive(true));
  }, []);

  useEffect(() => {
    if (!gift) return;
    if (gift.percent_complete !== prevPercent.current) {
      setPercentOpacity(0);
      const timer = window.setTimeout(() => setPercentOpacity(1), 50);
      prevPercent.current = gift.percent_complete;
      return () => window.clearTimeout(timer);
    }
  }, [gift?.percent_complete]);

  function handleClose() {
    setActive(false);
    window.setTimeout(onClose, 340);
  }

  function handleCopyPhone() {
    if (!gift?.payment_phone) return;
    navigator.clipboard.writeText(gift.payment_phone).then(() => {
      setPhoneCopied(true);
      window.setTimeout(() => setPhoneCopied(false), 2000);
    }).catch(() => {});
  }

  function handleCancelGift() {
    if (!cancelConfirming) {
      setCancelConfirming(true);
      return;
    }
    cancelMutation.mutate(undefined, { onSuccess: () => handleClose() });
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
      onSuccess: () => setJoinAmount(""),
    });
  }

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={handleClose}>
      <div
        className={`modal-sheet ${active ? "visible" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <h3 className="modal-title font-bold text-base mb-4 text-center">{t("groupGift")}</h3>

        {giftQuery.isPending ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
          </div>
        ) : !gift ? (
          <p className="text-sm text-muted text-center py-6">{t("giftNotActive")}</p>
        ) : (
          <div className="flex flex-col gap-4">
            {/* collection type badge */}
            <div className="flex justify-center">
              <span className="text-xs font-semibold text-muted bg-muted/10 px-3 py-1 rounded-full">
                {gift.collection_type === "immediate"
                  ? t("collectionTypeImmediate")
                  : t("collectionTypeCommit")}
              </span>
            </div>

            {/* progress section */}
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted">{t("collected")}</span>
                <span className="font-semibold text-foreground">{gift.collected_amount}</span>
              </div>
              {gift.total_amount ? (
                <div className="flex justify-between text-sm">
                  <span className="text-muted">{t("target")}</span>
                  <span className="font-semibold text-foreground">{gift.total_amount}</span>
                </div>
              ) : null}

              <div className="w-full h-2 rounded-full bg-muted/30 overflow-hidden mt-1">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
                  style={{ width: `${Math.min(100, gift.percent_complete)}%` }}
                />
              </div>

              <div className="flex justify-between items-center text-xs">
                <span
                  className="text-muted transition-opacity duration-300"
                  style={{ opacity: percentOpacity }}
                >
                  {gift.percent_complete >= 100
                    ? t("giftComplete")
                    : t("giftProgress").replace("{percent}", String(gift.percent_complete))}
                </span>
                <span className="text-muted">
                  {t("contributors")}: {gift.contributor_count}
                </span>
              </div>
            </div>

            {/* state-dependent action panel */}
            <div className="border-t border-border pt-4">
              {renderActionPanel()}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  function renderPaymentDetails() {
    if (!gift) return null;
    return (
      <div className="flex flex-col gap-2 bg-muted/5 rounded-2xl p-4 border border-border">
        <p className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">
          {t("organizerRequisites")}
        </p>
        {gift.payment_method ? (
          <p className="text-sm text-foreground">{gift.payment_method}</p>
        ) : null}
        {gift.payment_phone ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-foreground">{gift.payment_phone}</p>
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
          <p className="text-xs text-muted mt-1">{gift.payment_comment}</p>
        ) : null}
      </div>
    );
  }

  function renderActionPanel() {
    if (!gift) return null;

    // CASE H — gift finished
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

    // CASE A — organizer
    if (gift.is_organizer) {
      return (
        <div className="flex flex-col gap-3">
          {renderPaymentDetails()}

          {cancelConfirming ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted text-center">{t("confirmCancelGift")}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 h-11 rounded-xl bg-muted/10 text-muted text-sm font-medium"
                  onClick={() => setCancelConfirming(false)}
                >
                  {t("cancelButton")}
                </button>
                <button
                  type="button"
                  className="theme-confirm-danger flex-1 h-11 rounded-xl text-sm font-bold disabled:opacity-60"
                  disabled={cancelMutation.isPending}
                  onClick={handleCancelGift}
                >
                  {cancelMutation.isPending ? t("deleting") : t("cancelGiftButton")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="theme-press-danger w-full h-11 rounded-xl text-sm font-medium"
              onClick={() => setCancelConfirming(true)}
            >
              {t("cancelGiftButton")}
            </button>
          )}
        </div>
      );
    }

    const contrib = gift.my_contribution;

    // CASE B — contributor, waiting_transfer (immediate)
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

    // CASE C — contributor, waiting_confirmation (immediate)
    if (gift.is_contributor && contrib?.status === "waiting_confirmation") {
      return (
        <div className="flex flex-col items-center gap-3 py-2">
          <div className="w-6 h-6 rounded-full border-2 border-muted border-t-primary animate-spin" />
          <p className="text-sm text-muted text-center">{t("waitingConfirmation")}</p>
        </div>
      );
    }

    // CASE D — contributor, confirmed (immediate)
    if (gift.is_contributor && contrib?.status === "confirmed") {
      return (
        <p className="text-sm font-semibold text-center" style={{ color: "var(--color-success, #22c55e)" }}>
          {t("transferConfirmedStatus")}
        </p>
      );
    }

    // CASE E — contributor, pledged (commit)
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

    // CASE F — contributor, notified (commit, goal reached)
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

    // CASE G — not organizer, not contributor, gift active
    if (!gift.is_organizer && !gift.is_contributor && gift.status === "active") {
      return (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">
              {t("amountLabel")}
            </label>
            <input
              type="number"
              min={1}
              className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder={t("amountPlaceholder")}
              value={joinAmount}
              onChange={(e) => setJoinAmount(e.currentTarget.value)}
            />
          </div>
          <button
            type="button"
            className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold disabled:opacity-60"
            disabled={joinMutation.isPending || !joinAmount || parseFloat(joinAmount) < 1}
            onClick={handleJoin}
          >
            {joinMutation.isPending ? t("saving") : t("confirmJoin")}
          </button>
        </div>
      );
    }

    return null;
  }
}
