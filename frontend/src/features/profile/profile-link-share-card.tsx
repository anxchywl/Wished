"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/useTranslation";

type ProfileLinkShareCardProps = {
  publicUsername?: string | null;
  publicProfileUrl?: string | null;
  telegramStartappUrl?: string | null;
  className?: string;
};

type TelegramShareWindow = Window & {
  Telegram?: {
    WebApp?: {
      openTelegramLink?: (url: string) => void;
    };
  };
};

/**
 * compact public profile link share card
 */
export function ProfileLinkShareCard({
  publicUsername,
  publicProfileUrl,
  telegramStartappUrl,
  className = "",
}: ProfileLinkShareCardProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<string | null>(null);
  const profileLinkUrl = telegramStartappUrl || buildTelegramStartappUrl(publicUsername) || publicProfileUrl;

  if (!profileLinkUrl) return null;

  async function copyLink() {
    if (!profileLinkUrl) return false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(profileLinkUrl);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = profileLinkUrl;
        textarea.setAttribute("readonly", "true");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setStatus(t("profileLinkCopied"));
      window.setTimeout(() => setStatus(null), 1800);
      return true;
    } catch {
      setStatus(t("unableToCopyLink"));
      window.setTimeout(() => setStatus(null), 2200);
      return false;
    }
  }

  async function handleShare() {
    if (!profileLinkUrl) return;
    const shareTitle = t("wishedProfile");
    const telegramShareUrl =
      `https://t.me/share/url?url=${encodeURIComponent(profileLinkUrl)}` +
      `&text=${encodeURIComponent(shareTitle)}`;
    const webApp = (window as TelegramShareWindow).Telegram?.WebApp;

    if (webApp?.openTelegramLink) {
      webApp.openTelegramLink(telegramShareUrl);
      return;
    }

    if (navigator.share) {
      try {
        await navigator.share({ title: shareTitle, url: profileLinkUrl });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
      }
    }

    await copyLink();
  }

  return (
    <section className={`profile-link-share-card ${className}`}>
      <div className="profile-link-share-main">
        <span className="profile-link-share-label">{t("wishedProfile")}</span>
        <span className="profile-link-share-url">{profileLinkUrl}</span>
        {status ? <span className="profile-link-share-status">{status}</span> : null}
      </div>
      <div className="profile-link-share-actions">
        <button type="button" className="profile-link-share-button" onClick={copyLink}>
          {t("copyLink")}
        </button>
        <button type="button" className="profile-link-share-button profile-link-share-primary" onClick={handleShare}>
          {t("share")}
        </button>
      </div>
    </section>
  );
}

function buildTelegramStartappUrl(publicUsername?: string | null) {
  const normalizedUsername = publicUsername?.trim().replace(/^@/, "").toLowerCase();
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME?.trim().replace(/^@/, "");
  if (!normalizedUsername || !botUsername || !/^[a-z0-9_]{3,32}$/.test(normalizedUsername)) {
    return null;
  }
  return `https://t.me/${botUsername}?startapp=p_${encodeURIComponent(normalizedUsername)}`;
}
