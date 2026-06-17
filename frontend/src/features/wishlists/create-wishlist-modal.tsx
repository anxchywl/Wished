"use client";

import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ImageCropperModal } from "@/components/ui/image-cropper";
import { finalizeTextInput, normalizeTextInput } from "@/lib/forms/input-normalize";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { DEFAULT_COVER_GRADIENT, compressImage } from "./utils";
import type { WishlistVisibility } from "./types";
import { getWishlistCoverStyle } from "./wishlist-visuals";
import { useModalFocusMode } from "./use-modal-focus-mode";
import { useUIStore } from "@/stores/ui-store";

type CreateWishlistModalProps = {
  open: boolean;
  onClose: () => void;
  onCreate: (title: string, description: string | null, cover: string, visibility: WishlistVisibility) => void;
  isPending: boolean;
};

/**
 * slide up modal to create a wishlist in two stages
 */
export function CreateWishlistModal({ open, onClose, onCreate, isPending }: CreateWishlistModalProps) {
  const { t } = useTranslation();
  const fallbackCover = useUIStore((state) => state.coverStyle);
  const focusMode = useModalFocusMode();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [title, setTitle] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [selectedCover, setSelectedCover] = useState<string>("");
  const [visibility, setVisibility] = useState<WishlistVisibility>("public");
  const [active, setActive] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [pendingCropFile, setPendingCropFile] = useState<File | null>(null);

  useEffect(() => {
    if (open) {
      setActive(true);
      setStep(1);
      setTitle("");
      setDescription("");
      setSelectedCover("");
      setVisibility("public");
      setPendingCropFile(null);
    } else {
      setActive(false);
    }
  }, [open]);

  if (!open) return null;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingCropFile(file);
    e.target.value = "";
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleanTitle = finalizeTextInput(title, 120);
    const cleanDescription = finalizeTextInput(description, 1000);

    if (step === 1) {
      setTitle(cleanTitle);
      setDescription(cleanDescription);
      if (cleanTitle) {
        setStep(2);
      }
      return;
    }
    onCreate(cleanTitle, cleanDescription || null, selectedCover || DEFAULT_COVER_GRADIENT, visibility);
  }

  function handleCancel() {
    if (focusMode.isFocusMode) {
      focusMode.clearFocus();
      return;
    }

    onClose();
  }

  return (
    <div
      className={`modal-backdrop ${active ? "visible" : ""}`}
      onClick={onClose}
    >
      <div
        className={`modal-sheet ${active ? "visible" : ""} ${focusMode.isFocusMode ? "keyboard-focus-mode" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-handle" />
        <h3 className={`modal-title font-bold text-base mb-3 text-center ${focusMode.sectionClass("titleText")}`}>
          {step === 1 ? t("createNewWishlist") : t("configureWishlist")}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="public-nav-viewport" style={{ maxHeight: "none", overflow: "visible", padding: 0 }}>
            {step === 1 ? (
              <div
                key="wishlist-details-step"
                className="public-nav-frame public-nav-enter-back flex flex-col gap-3"
              >
                <div className={`flex flex-col gap-1 ${focusMode.sectionClass("title")}`}>
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("wishlistTitleLabel")}</label>
                  <input
                    type="text"
                    required
                    className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    value={title}
                    onBlur={() => {
                      setTitle((current) => finalizeTextInput(current, 120));
                      focusMode.onFieldBlur();
                    }}
                    onChange={(e) => setTitle(normalizeTextInput(e.currentTarget.value, 120))}
                    maxLength={120}
                    {...focusMode.fieldFocusProps("title")}
                  />
                </div>

                <div className={`flex flex-col gap-1 ${focusMode.sectionClass("description")}`}>
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("descriptionLabel")}</label>
                  <textarea
                    className="min-h-20 max-h-28 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                    value={description}
                    onBlur={() => {
                      setDescription((current) => finalizeTextInput(current, 1000));
                      focusMode.onFieldBlur();
                    }}
                    onChange={(e) => setDescription(normalizeTextInput(e.currentTarget.value, 1000))}
                    maxLength={1000}
                    {...focusMode.fieldFocusProps("description")}
                  />
                </div>

                <div className="border-t border-border mt-2 pt-2 relative overflow-hidden">
                  <div
                    className={`modal-footer-transition ${
                      focusMode.isFocusMode
                        ? "opacity-100 max-h-12 scale-100 mt-1"
                        : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
                    }`}
                  >
                    <Button
                      type="button"
                      className="w-full rounded-xl h-10 text-sm"
                      onClick={focusMode.clearFocus}
                    >
                      {t("done") ?? "Done"}
                    </Button>
                  </div>
                  <div
                    className={`flex gap-2 modal-footer-transition ${
                      !focusMode.isFocusMode
                        ? "opacity-100 max-h-12 scale-100"
                        : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
                    }`}
                  >
                    <button
                      type="button"
                      className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                      onClick={handleCancel}
                    >
                      {t("cancelButton") ?? "Cancel"}
                    </button>
                    <Button
                      type="submit"
                      className="flex-1 rounded-xl h-10 text-sm"
                      disabled={!title.trim()}
                    >
                      {t("next") ?? "Next"}
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div
                key="wishlist-cover-step"
                className="public-nav-frame public-nav-enter-forward flex flex-col gap-3"
              >
                {/* upload cover photo section */}
                <div className="flex flex-col gap-1.5 modal-focus-section">
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("coverStyle") ?? "Cover Photo"}</label>
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="image/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <div
                    className={selectedCover ? "wish-upload-cover-preview relative h-28 rounded-xl overflow-hidden border border-border text-left" : "wish-upload-cover-surface relative h-28 rounded-xl overflow-hidden cursor-pointer flex flex-col items-center justify-center gap-1 transition-all"}
                    onClick={() => fileInputRef.current?.click()}
                    style={
                      selectedCover
                        ? { backgroundImage: `url(${selectedCover})`, backgroundSize: "cover", backgroundPosition: "center", borderStyle: "solid" }
                        : getWishlistCoverStyle({ coverStyle: DEFAULT_COVER_GRADIENT, fallback: fallbackCover })
                    }
                  >
                    {selectedCover ? (
                      <span className="wish-upload-cover-preview-label">{t("changeCover") ?? "Change Cover"}</span>
                    ) : (
                      <>
                        <span className="wish-upload-cover-label">
                          {compressing ? (t("compressing") ?? "Uploading...") : (t("uploadCover") ?? "Upload Cover")}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* horizontal privacy selector */}
                <div className="flex flex-col gap-1.5 mt-1">
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("privacy") ?? "Privacy"}</label>
                  <div className="flex gap-2 w-full">
                    {/* public */}
                    <button
                      type="button"
                      className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-3 rounded-2xl border transition-all ${
                        visibility === "public"
                          ? "privacy-option-active"
                          : "bg-muted/10 border-border text-muted hover:bg-muted/20"
                      }`}
                      onClick={() => setVisibility("public")}
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <span className="text-xs font-semibold">{t("public") ?? "Public"}</span>
                    </button>

                    {/* private */}
                    <button
                      type="button"
                      className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-3 rounded-2xl border transition-all ${
                        visibility === "private"
                          ? "privacy-option-active"
                          : "bg-muted/10 border-border text-muted hover:bg-muted/20"
                      }`}
                      onClick={() => setVisibility("private")}
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                      </svg>
                      <span className="text-xs font-semibold">{t("private") ?? "Private"}</span>
                    </button>
                  </div>
                </div>

                <div className="flex gap-2 mt-2">
                  <button
                    type="button"
                    className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                    onClick={() => setStep(1)}
                  >
                    {t("back") ?? "Back"}
                  </button>
                  <Button
                    type="submit"
                    className="flex-1 rounded-xl h-10 text-sm"
                    disabled={isPending || compressing}
                  >
                    {isPending ? (t("creating") ?? "Creating...") : (t("createWishlistButton") ?? "Create")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </form>
      </div>
      {pendingCropFile && (
        <ImageCropperModal
          file={pendingCropFile}
          onCrop={async (croppedFile) => {
            setPendingCropFile(null);
            try {
              setCompressing(true);
              const dataUrl = await compressImage(croppedFile, 400, 400, 0.8);
              setSelectedCover(dataUrl);
            } catch (err) {
              console.error("Image compression failed", err);
            } finally {
              setCompressing(false);
            }
          }}
          onCancel={() => setPendingCropFile(null)}
        />
      )}
    </div>
  );
}
