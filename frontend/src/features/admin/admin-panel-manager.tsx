"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "@/lib/i18n/useTranslation";
import {
  useAdminStats,
  useAdminUsers,
  useAdminWishlists,
  useAdminWishes,
  useAuditLogs,
  useBlockUser,
  useUnblockUser,
} from "./hooks";
import type { AdminUserItem, AdminWishlistItem, AdminWishItem, AuditLogItem } from "./api";

type Tab = "dashboard" | "users" | "content" | "logs";

export function AdminPanelManager() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [userSearch, setUserSearch] = useState("");

  return (
    <section className="panel admin-panel">
      <div className="admin-tabs">
        {(["dashboard", "users", "content", "logs"] as Tab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`admin-tab${activeTab === tab ? " active" : ""}`}
          >
            {tab === "dashboard" && t("adminTabDashboard")}
            {tab === "users" && t("adminTabUsers")}
            {tab === "content" && t("adminTabContent")}
            {tab === "logs" && t("adminTabLogs")}
          </button>
        ))}
      </div>

      <div className="admin-tab-content">
        {activeTab === "dashboard" && <DashboardTab />}
        {activeTab === "users" && <UsersTab search={userSearch} setSearch={setUserSearch} />}
        {activeTab === "content" && <ContentTab />}
        {activeTab === "logs" && <LogsTab />}
      </div>
    </section>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-value">{value}</div>
      <div className="admin-stat-label">{label}</div>
    </div>
  );
}

function DashboardTab() {
  const { t } = useTranslation();
  const { data: stats, isLoading, error } = useAdminStats();

  if (isLoading) return <p className="admin-state">{t("adminLoading")}</p>;
  if (error || !stats) return <p className="admin-state admin-state-error">{t("adminAccessDenied")}</p>;

  return (
    <div className="admin-stats-grid">
      <StatCard label={t("adminTotalUsers")} value={stats.total_users} />
      <StatCard label={t("adminActiveUsers")} value={stats.active_users} />
      <StatCard label={t("adminTotalWishlists")} value={stats.total_wishlists} />
      <StatCard label={t("adminTotalWishes")} value={stats.total_wishes} />
      <StatCard label={t("adminActiveWishes")} value={stats.active_wishes} />
      <StatCard label={t("adminTotalReservations")} value={stats.total_reservations} />
      <StatCard label={t("adminTotalMedia")} value={stats.total_media} />
      <StatCard label={t("adminTotalFollows")} value={stats.total_follows} />
    </div>
  );
}

const SEARCH_MAX_LENGTH = 64;
const SEARCH_ALLOWED_RE = /[<>"'`;\\]/g;

function sanitizeSearch(raw: string): string {
  // strip leading spaces; allow at most one trailing space; remove injection chars
  return raw
    .replace(SEARCH_ALLOWED_RE, "")
    .replace(/^ +/, "")
    .replace(/ {2,}$/, " ")
    .slice(0, SEARCH_MAX_LENGTH);
}

function UsersTab({ search, setSearch }: { search: string; setSearch: (v: string) => void }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState(search);
  const { data: users, isLoading } = useAdminUsers(search || undefined);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSearch(query.trim());
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [query, setSearch]);

  function handleSearchChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(sanitizeSearch(e.target.value));
  }

  return (
    <div>
      <label className="admin-search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          type="search"
          value={query}
          onChange={handleSearchChange}
          placeholder={t("adminSearchPlaceholder")}
          maxLength={SEARCH_MAX_LENGTH}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          aria-label={t("adminSearchPlaceholder")}
        />
        {query && (
          <button type="button" onClick={() => setQuery("")} aria-label={t("clearSearch")}>
            ×
          </button>
        )}
      </label>
      {isLoading && <p className="admin-state">{t("adminLoading")}</p>}
      {users && users.length === 0 && <p className="admin-state">{t("adminNoUsers")}</p>}
      {users && users.map((u) => <UserRow key={u.id} user={u} searchQuery={search || undefined} />)}
    </div>
  );
}

type ModerationDialogState =
  | { type: "block"; userId: string }
  | { type: "unblock"; userId: string }
  | null;

function ModerationDialog({
  dialog,
  onClose,
  searchQuery,
}: {
  dialog: ModerationDialogState;
  onClose: () => void;
  searchQuery?: string;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const blockMutation = useBlockUser(searchQuery);
  const unblockMutation = useUnblockUser(searchQuery);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (dialog) {
      setReason("");
      setReasonError(false);
      window.setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [dialog]);

  if (!dialog) return null;

  const isBlock = dialog.type === "block";
  const isPending = blockMutation.isPending || unblockMutation.isPending;

  async function handleConfirm() {
    if (!dialog) return;
    if (isBlock && !reason.trim()) {
      setReasonError(true);
      return;
    }
    try {
      if (isBlock) {
        await blockMutation.mutateAsync({ userId: dialog.userId, reason: reason.trim() });
      } else {
        await unblockMutation.mutateAsync({ userId: dialog.userId });
      }
      onClose();
    } catch {
      // error visible via mutation state; dialog stays open
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed", inset: 0, zIndex: 9000,
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.55)", padding: 20,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: "var(--tg-theme-bg-color, #fff)",
        borderRadius: 16, padding: 24, width: "100%", maxWidth: 340,
        display: "flex", flexDirection: "column", gap: 16,
      }}>
        <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "var(--tg-theme-text-color)" }}>
          {isBlock ? t("adminBlockConfirmTitle") : t("adminUnblockConfirmTitle")}
        </h2>
        <p style={{ margin: 0, fontSize: 14, color: "var(--tg-theme-hint-color)", lineHeight: 1.5 }}>
          {isBlock ? t("adminBlockConfirmBody") : t("adminUnblockConfirmBody")}
        </p>
        {isBlock && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: "var(--tg-theme-text-color)" }}>
              {t("adminBlockReasonLabel")}
            </label>
            <textarea
              ref={inputRef}
              value={reason}
              onChange={(e) => { setReason(e.target.value); setReasonError(false); }}
              placeholder={t("adminBlockReasonPlaceholder")}
              rows={3}
              maxLength={500}
              style={{
                resize: "none", borderRadius: 8, padding: "8px 10px",
                fontSize: 14, border: `1px solid ${reasonError ? "var(--tg-theme-destructive-text-color, red)" : "var(--tg-theme-hint-color, #ccc)"}`,
                background: "var(--tg-theme-secondary-bg-color, #f5f5f5)",
                color: "var(--tg-theme-text-color)",
              }}
            />
            {reasonError && (
              <span style={{ fontSize: 12, color: "var(--tg-theme-destructive-text-color, red)" }}>
                {t("adminBlockReasonRequired")}
              </span>
            )}
          </div>
        )}
        <div style={{ display: "flex", gap: 10 }}>
          <button
            type="button"
            disabled={isPending}
            onClick={onClose}
            style={{
              flex: 1, padding: "10px 0", borderRadius: 10, fontWeight: 600, fontSize: 14,
              background: "var(--tg-theme-secondary-bg-color, #f0f0f0)",
              color: "var(--tg-theme-text-color)", border: "none", cursor: "pointer",
            }}
          >
            {t("adminCancel")}
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={handleConfirm}
            style={{
              flex: 1, padding: "10px 0", borderRadius: 10, fontWeight: 600, fontSize: 14,
              background: isBlock ? "var(--tg-theme-destructive-text-color, #e53935)" : "var(--tg-theme-button-color, #6B7EE8)",
              color: "#fff", border: "none", cursor: isPending ? "not-allowed" : "pointer",
              opacity: isPending ? 0.6 : 1,
            }}
          >
            {t("adminConfirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

function UserRow({ user, searchQuery }: { user: AdminUserItem; searchQuery?: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [dialog, setDialog] = useState<ModerationDialogState>(null);
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username || `tg:${user.telegram_id}`;

  async function copyUsername() {
    if (!user.username) return;
    const username = `@${user.username}`;
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(username);
    } else {
      const input = document.createElement("textarea");
      input.value = username;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  const initials = (user.first_name?.[0] ?? user.username?.[0] ?? "?").toUpperCase();

  return (
    <>
      <ModerationDialog dialog={dialog} onClose={() => setDialog(null)} searchQuery={searchQuery} />
      <article
        className="admin-list-card"
        style={{
          display: "flex", gap: "10px", alignItems: "flex-start",
          opacity: user.is_blocked ? 0.75 : 1,
          borderLeft: user.is_blocked ? "3px solid var(--tg-theme-destructive-text-color, #e53935)" : undefined,
        }}
      >
        <div style={{ flexShrink: 0, width: 36, height: 36, borderRadius: "50%", overflow: "hidden", background: "var(--tg-theme-button-color, #6B7EE8)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 600, color: "#fff" }}>
          {user.photo_url
            ? <img src={user.photo_url} alt={initials} width={36} height={36} style={{ objectFit: "cover" }} referrerPolicy="no-referrer" />
            : initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span className="admin-list-title" style={{ margin: 0 }}>{name}</span>
            {user.is_blocked && (
              <span style={{
                fontSize: 11, fontWeight: 700, padding: "2px 6px", borderRadius: 4,
                background: "var(--tg-theme-destructive-text-color, #e53935)", color: "#fff",
                textTransform: "uppercase", letterSpacing: "0.04em",
              }}>
                {t("adminBlockedBadge")}
              </span>
            )}
          </div>
          {user.username && (
            <button type="button" className="admin-username" onClick={copyUsername} title={copied ? t("adminUsernameCopied") : t("adminCopyUsername")}>
              @{user.username}
            </button>
          )}
          <div className="admin-list-meta">
            ID: {user.telegram_id} · {user.wishlist_count} {t("adminWishlistsCount")} · {user.wish_count} {t("adminWishesCount")}
          </div>
          <div className="admin-list-meta">
            {t("adminJoined")}: {new Date(user.created_at).toLocaleDateString()}
            {user.last_login_at && ` · ${t("adminLastLogin")}: ${new Date(user.last_login_at).toLocaleDateString()}`}
          </div>
          {user.is_blocked && user.blocked_reason && (
            <div className="admin-list-meta" style={{ color: "var(--tg-theme-destructive-text-color, #e53935)" }}>
              {user.blocked_reason}
            </div>
          )}
        </div>
        <div style={{ flexShrink: 0 }}>
          {user.is_blocked ? (
            <button
              type="button"
              onClick={() => setDialog({ type: "unblock", userId: user.id })}
              style={{
                padding: "6px 12px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: "var(--tg-theme-button-color, #6B7EE8)", color: "#fff",
                border: "none", cursor: "pointer",
              }}
            >
              {t("adminUnblockUser")}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setDialog({ type: "block", userId: user.id })}
              style={{
                padding: "6px 12px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                background: "var(--tg-theme-destructive-text-color, #e53935)", color: "#fff",
                border: "none", cursor: "pointer",
              }}
            >
              {t("adminBlockUser")}
            </button>
          )}
        </div>
      </article>
    </>
  );
}

function ContentTab() {
  const { t } = useTranslation();
  const [view, setView] = useState<"wishlists" | "wishes">("wishlists");
  const { data: wishlists, isLoading: wlLoading } = useAdminWishlists();
  const { data: wishes, isLoading: wLoading } = useAdminWishes();

  return (
    <div>
      <div className="admin-segmented">
        {(["wishlists", "wishes"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className={`admin-segment${view === v ? " active" : ""}`}
          >
            {v === "wishlists" ? t("adminWishlists") : t("adminWishes")}
          </button>
        ))}
      </div>

      {view === "wishlists" && (
        <>
          {wlLoading && <p className="admin-state">{t("adminLoading")}</p>}
          {wishlists && wishlists.length === 0 && <p className="admin-state">{t("adminNoWishlists")}</p>}
          {wishlists && wishlists.map((wl) => <WishlistRow key={wl.id} item={wl} />)}
        </>
      )}

      {view === "wishes" && (
        <>
          {wLoading && <p className="admin-state">{t("adminLoading")}</p>}
          {wishes && wishes.length === 0 && <p className="admin-state">{t("adminNoWishes")}</p>}
          {wishes && wishes.map((w) => <WishRow key={w.id} item={w} />)}
        </>
      )}
    </div>
  );
}

function WishlistRow({ item }: { item: AdminWishlistItem }) {
  const { t } = useTranslation();
  const visibilityMap: Record<string, string> = {
    public: t("adminVisibilityPublic"),
    private: t("adminVisibilityPrivate"),
  };
  return (
    <article className="admin-list-card">
      <div className="admin-list-title">{item.title}</div>
      <div className="admin-list-meta">
        {t("adminOwner")}: {item.owner_username ? `@${item.owner_username}` : `tg:${item.owner_telegram_id}`} · {item.wish_count} {t("adminWishesCount")} · {visibilityMap[item.visibility] ?? item.visibility}
      </div>
      <div className="admin-list-meta">
        {new Date(item.created_at).toLocaleDateString()}
      </div>
    </article>
  );
}

function WishRow({ item }: { item: AdminWishItem }) {
  const { t } = useTranslation();
  const statusMap: Record<string, string> = {
    active: t("adminStatusActive"),
    completed: t("adminStatusCompleted"),
    archived: t("adminStatusArchived"),
  };
  return (
    <article className="admin-list-card">
      <div className="admin-list-title">{item.title}</div>
      <div className="admin-list-meta">
        {t("adminOwner")}: tg:{item.owner_telegram_id} · {statusMap[item.status] ?? item.status} · {item.image_count} {t("adminImagesCount")}
        {item.has_reservation && ` · ${t("adminReserved")}`}
      </div>
      <div className="admin-list-meta">
        {new Date(item.created_at).toLocaleDateString()}
      </div>
    </article>
  );
}

function LogsTab() {
  const { t } = useTranslation();
  const { data: logs, isLoading } = useAuditLogs();

  if (isLoading) return <p className="admin-state">{t("adminLoading")}</p>;
  if (!logs || logs.length === 0) return <p className="admin-state">{t("adminNoAuditLogs")}</p>;

  return (
    <div>
      {logs.map((log) => <LogRow key={log.id} log={log} />)}
    </div>
  );
}

function LogRow({ log }: { log: AuditLogItem }) {
  const { t } = useTranslation();
  const actionMap: Record<string, string> = {
    viewed_stats: t("adminActionViewedStats"),
    viewed_users: t("adminActionViewedUsers"),
    viewed_wishlists: t("adminActionViewedWishlists"),
    viewed_wishes: t("adminActionViewedWishes"),
    viewed_media: t("adminActionViewedMedia"),
    blocked_user: t("adminActionBlocked"),
    unblocked_user: t("adminActionUnblocked"),
  };
  const label = actionMap[log.action] ?? log.action;
  const actor = log.actor_telegram_id ? `tg:${log.actor_telegram_id}` : t("adminSystem");
  return (
    <article className="admin-list-card">
      <div className="admin-list-title">{label}</div>
      <div className="admin-list-meta">
        {actor}
        {log.target_type && ` → ${log.target_type}${log.target_id ? `:${log.target_id}` : ""}`}
        {" · "}
        {new Date(log.created_at).toLocaleString()}
      </div>
    </article>
  );
}
