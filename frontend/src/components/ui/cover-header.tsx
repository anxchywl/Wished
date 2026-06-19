"use client";

import { useState } from "react";
import { UIControls } from "@/components/ui/controls";
import { BirthdayPicker } from "@/components/ui/birthday-picker";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { useProfileQuery, useUpdateBirthdayMutation } from "@/features/profile";
import { useTranslation } from "@/lib/i18n/useTranslation";

type CoverHeaderProps = {
  title: string;
  hideProfile?: boolean;
};

/**
 * gradient cover header with user profile row
 */
export function CoverHeader({ title, hideProfile = false }: CoverHeaderProps) {
  const { t } = useTranslation();
  const accessToken = useAuthStore((state) => state.accessToken);
  const coverStyle = useUIStore((state) => state.coverStyle);
  const { data: profile } = useProfileQuery(accessToken);
  const updateBirthday = useUpdateBirthdayMutation();
  const [pickerOpen, setPickerOpen] = useState(false);

  // derive display name
  const displayName = profile?.first_name
    ? [profile.first_name, profile.last_name].filter(Boolean).join(" ")
    : (profile?.username ? `@${profile.username}` : null);

  // derive initials for fallback avatar
  const initials = (displayName ?? "?")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  // format birthday for display
  function formatBirthday(raw: string | null | undefined) {
    if (!raw) return null;
    const [y, m, d] = raw.split("-");
    const months = t("months").split(",");
    return `${parseInt(d, 10)} ${months[parseInt(m, 10) - 1]} ${y}`;
  }

  function handleSave(date: string) {
    if (!accessToken) return;
    updateBirthday.mutate({ accessToken, birthday: date });
    setPickerOpen(false);
  }

  return (
    <>
      <header
        className="cover cover-compact"
        style={{
          "--fallback-angle": `${coverStyle.angle}deg`,
          "--fallback-a": coverStyle.a,
          "--fallback-b": coverStyle.b,
          "--fallback-c": coverStyle.c,
          "--fallback-d": coverStyle.d,
        } as React.CSSProperties}
      >
        <UIControls />

        {/* profile row */}
        {profile && !hideProfile && (
          <div className="cover-profile-row">
            {/* avatar */}
            <div className="cover-avatar">
              {profile.photo_url ? (
                <>
                  <img
                    src={profile.photo_url}
                    alt={displayName ?? ""}
                    className="cover-avatar-img"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                      (e.currentTarget.nextElementSibling as HTMLElement | null)?.style &&
                        ((e.currentTarget.nextElementSibling as HTMLElement).style.display = "flex");
                    }}
                  />
                  <span className="cover-avatar-initials" style={{ display: "none" }}>{initials}</span>
                </>
              ) : (
                <span className="cover-avatar-initials">{initials}</span>
              )}
            </div>

            {/* name + birthday */}
            <div className="cover-profile-meta">
              <p className="cover-profile-name">
                {displayName ?? profile.username ?? "—"}
              </p>
              <button
                className="cover-birthday-btn"
                type="button"
                onClick={() => setPickerOpen(true)}
                aria-label="Set birthday"
              >
                {profile.birthday ? (
                  <span className="cover-birthday-value">
                    {formatBirthday(profile.birthday)}
                  </span>
                ) : (
                  <span className="cover-birthday-add">+ {t("addBirthday")}</span>
                )}
              </button>
            </div>
          </div>
        )}

        {/* page title */}
        {title && <h1 className="cover-title">{title}</h1>}
      </header>

      <BirthdayPicker
        open={pickerOpen}
        initial={profile?.birthday}
        onClose={() => setPickerOpen(false)}
        onSave={handleSave}
      />
    </>
  );
}
