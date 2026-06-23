"use client";

/* eslint-disable @next/next/no-img-element -- minio urls preview uploads */

import { FormEvent, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  useCreateWishMutation,
  useDeleteWishMutation,
  useDeleteWishImageMutation,
  useUpdateWishMutation,
  useUploadWishImageMutation,
  useWishesQuery,
} from "@/features/wishes/hooks";
import type { Wish } from "@/features/wishes/types";
import { useWishlistsQuery } from "@/features/wishlists/hooks";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { UIControls } from "@/components/ui/controls";
import {
  finalizePriceInput,
  finalizeTextInput,
  normalizeCurrencyInput,
  normalizePriceInput,
  normalizePriorityInput,
  normalizeTextInput,
} from "@/lib/forms/input-normalize";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";

type WishManagerProps = {
  wishlistId: string;
};

/**
 * manage wishes
 */
// wishes manager component
export function WishManager({ wishlistId }: WishManagerProps) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const wishesQuery = useWishesQuery(wishlistId);
  const wishlistsQuery = useWishlistsQuery();
  const createMutation = useCreateWishMutation(wishlistId);
  const updateMutation = useUpdateWishMutation(wishlistId);
  const deleteMutation = useDeleteWishMutation(wishlistId);
  const uploadImageMutation = useUploadWishImageMutation(wishlistId);
  const deleteImageMutation = useDeleteWishImageMutation(wishlistId);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("");
  const { t } = useTranslation();
  const coverStyle = useUIStore((state) => state.coverStyle);
  const guardDecision = isAuthPending(authStatus)
    ? "startup"
    : isAuthFailure(authStatus) || (authStatus !== "authenticated" && !accessToken)
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "WishManager",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  /**
   * create wish
   */
  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanTitle = finalizeTextInput(title, 160);
    const normalizedPrice = finalizePriceInput(price);
    const normalizedCurrency = normalizeCurrencyInput(currency);
    if (!cleanTitle) {
      setTitle("");
      return;
    }
    createMutation.mutate(
      {
        title: cleanTitle,
        priority,
        price: normalizedPrice || null,
        currency: normalizedPrice ? normalizedCurrency || "USD" : null,
      },
      {
        onSuccess: () => {
          setTitle("");
          setPriority(3);
          setPrice("");
          setCurrency("");
        },
      },
    );
  }

  if (guardDecision === "startup") {
    return (
      <main className="min-h-dvh px-5 py-6 flex items-center justify-center">
        <span className="auth-loading-spinner" />
      </main>
    );
  }

  if (guardDecision === "auth_required") {
    return (
      <main className="min-h-dvh px-5 py-6">
        <p className="text-sm text-muted">{t("authenticateBeforeEditingWishes")}</p>
      </main>
    );
  }

  return (
    <div className="min-h-dvh">
      <header
        className="cover"
        style={{
          "--fallback-angle": `${coverStyle.angle}deg`,
          "--fallback-a": coverStyle.a,
          "--fallback-b": coverStyle.b,
          "--fallback-c": coverStyle.c,
          "--fallback-d": coverStyle.d,
        } as React.CSSProperties}
      >
        <UIControls />
        <div className="flex justify-between items-end w-full max-w-screen-sm mx-auto">
          <div>
            <div className="eyebrow">{t("wished")}</div>
            <h1>{t("wishes")}</h1>
          </div>
          <div className="flex gap-2">
            <Link
              href="/wishlists"
              className="text-sm font-semibold bg-white/20 backdrop-blur-md text-white border border-white/20 px-4 py-2 rounded-xl hover:bg-white/30 transition-all"
            >
              {t("wishlists")}
            </Link>
          </div>
        </div>
      </header>

      <main className="content flex flex-col gap-4">
        <form className="panel flex flex-col gap-3" onSubmit={create}>
          <h3 className="text-sm font-bold border-b border-border pb-2 mb-1">{t("createNewWish")}</h3>
          <input
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            maxLength={160}
            onBlur={() => setTitle((current) => finalizeTextInput(current, 160))}
            onChange={(event) => setTitle(normalizeTextInput(event.currentTarget.value, 160))}
            placeholder={t("wishTitlePlaceholder")}
            required
            value={title}
          />
          <input
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            max={5}
            min={1}
            onChange={(event) => setPriority(normalizePriorityInput(event.currentTarget.value))}
            type="number"
            value={priority}
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              min={0}
              onBlur={() => setPrice((current) => finalizePriceInput(current))}
              onChange={(event) => setPrice(normalizePriceInput(event.currentTarget.value))}
              placeholder={t("pricePlaceholder")}
              step="0.01"
              type="number"
              value={price}
            />
            <input
              className="h-10 rounded-xl border border-border bg-background px-3 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary/50"
              maxLength={3}
              onChange={(event) => setCurrency(normalizeCurrencyInput(event.currentTarget.value))}
              placeholder="USD"
              value={currency}
            />
          </div>
          <Button disabled={createMutation.isPending} type="submit" className="rounded-xl">
            {t("createWishButton")}
          </Button>
        </form>

        {wishesQuery.isLoading ? <p className="text-sm text-muted text-center py-4">{t("loadingWishes")}</p> : null}
        {wishesQuery.isError ? <p className="text-sm text-muted text-center py-4">{t("unableToLoadWishes")}</p> : null}

        <div className="flex flex-col gap-3">
          {wishesQuery.data?.items.map((wish) => (
            <WishItem
              key={wish.id}
              onDelete={() => deleteMutation.mutate(wish.id)}
              onDeleteImage={(imageId) => deleteImageMutation.mutate({ wishId: wish.id, imageId })}
              onUploadImage={(file) => uploadImageMutation.mutate({ wishId: wish.id, file })}
              onUpdate={(input) => updateMutation.mutate({ id: wish.id, input })}
              selectableWishlists={wishlistsQuery.data?.items ?? []}
              wish={wish}
              isMutating={updateMutation.isPending || deleteMutation.isPending}
            />
          ))}
        </div>
      </main>
    </div>
  );
}

export type WishItemProps = {
  wish: Wish;
  selectableWishlists: Array<{ id: string; title: string }>;
  onUpdate: (input: {
    wishlist_id?: string;
    title?: string;
    priority?: number;
    price?: string | null;
    currency?: string | null;
  }) => void;
  onDelete: () => void;
  onUploadImage: (file: File) => void;
  onDeleteImage: (imageId: string) => void;
  isMutating?: boolean;
};

/**
 * edit wish item
 */
export function WishItem({
  wish,
  selectableWishlists,
  onUpdate,
  onDelete,
  onUploadImage,
  onDeleteImage,
  isMutating = false,
}: WishItemProps) {
  const [title, setTitle] = useState(wish.title ?? "");
  const [wishlistId, setWishlistId] = useState(wish.wishlist_id ?? "");
  const [priority, setPriority] = useState(wish.priority ?? 3);
  const [price, setPrice] = useState(wish.price ?? "");
  const [currency, setCurrency] = useState(wish.currency ?? "");
  const { t } = useTranslation();

  return (
    <article className="panel flex flex-col gap-3">
      <div className="flex flex-col gap-3">
        <input
          className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          maxLength={160}
          onBlur={() => setTitle((current) => finalizeTextInput(current, 160))}
          onChange={(event) => setTitle(normalizeTextInput(event.currentTarget.value, 160))}
          value={title}
        />
        <select
          className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none"
          onChange={(event) => setWishlistId(event.target.value)}
          value={wishlistId}
        >
          {selectableWishlists.map((wishlist) => (
            <option key={wishlist.id} value={wishlist.id}>
              {wishlist.title}
            </option>
          ))}
        </select>
        <input
          className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          max={5}
          min={1}
          onChange={(event) => setPriority(normalizePriorityInput(event.currentTarget.value))}
          type="number"
          value={priority}
        />
        <div className="grid grid-cols-2 gap-2">
          <input
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            min={0}
            onBlur={() => setPrice((current) => finalizePriceInput(current))}
            onChange={(event) => setPrice(normalizePriceInput(event.currentTarget.value))}
            step="0.01"
            type="number"
            value={price}
          />
          <input
            className="h-10 rounded-xl border border-border bg-background px-3 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary/50"
            maxLength={3}
            onChange={(event) => setCurrency(normalizeCurrencyInput(event.currentTarget.value))}
            value={currency}
          />
        </div>
        <div className="flex gap-2">
          <Button
            className="rounded-xl"
            disabled={isMutating}
            onClick={() => {
              const cleanTitle = finalizeTextInput(title, 160);
              const cleanPrice = finalizePriceInput(price);
              const cleanCurrency = normalizeCurrencyInput(currency);
              setTitle(cleanTitle);
              setPrice(cleanPrice);
              setCurrency(cleanCurrency);
              onUpdate({
                wishlist_id: wishlistId,
                title: cleanTitle,
                priority,
                price: cleanPrice || null,
                currency: cleanPrice ? cleanCurrency || "USD" : null,
              });
            }}
          >
            {t("saveButton")}
          </Button>
          <Button
            className="rounded-xl bg-destructive hover:bg-destructive/90"
            disabled={isMutating}
            onClick={onDelete}
          >
            {t("deleteButton")}
          </Button>
        </div>
        
        {wish.images.filter((img) => img.status === "ready").length > 0 ? (
          <div className="border-t border-border mt-2 pt-3 flex flex-col gap-2">
            {wish.images
              .filter((img) => img.status === "ready")
              .map((image) => (
                <div className="overflow-hidden rounded-xl border border-border bg-muted/10" key={image.id}>
                  <img
                    alt={image.file_name}
                    className="aspect-square w-full object-cover"
                    src={image.thumbnail_url ?? image.medium_url ?? undefined}
                  />
                  <button
                    className="w-full px-2 py-2 text-sm text-destructive hover:bg-destructive/10 font-semibold transition-colors"
                    onClick={() => onDeleteImage(image.id)}
                    type="button"
                  >
                    {t("deleteImageButton")}
                  </button>
                </div>
              ))}
          </div>
        ) : (
          <div className="border-t border-border mt-2 pt-3">
            <label className="text-sm font-semibold block mb-2" htmlFor={`image-${wish.id}`}>
              {t("imagesLabel")}
            </label>
            <input
              accept="image/jpeg,image/png,image/webp"
              className="text-sm block w-full text-muted file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
              id={`image-${wish.id}`}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  onUploadImage(file);
                  event.target.value = "";
                }
              }}
              type="file"
            />
          </div>
        )}
      </div>
    </article>
  );
}
