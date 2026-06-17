"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { useIsMutating } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
  DragStartEvent,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { UIControls } from "@/components/ui/controls";
import {
  finalizePriceInput,
  finalizeTextInput,
  normalizeCurrencyInput,
  normalizePriceInput,
  normalizeTextInput,
} from "@/lib/forms/input-normalize";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { useTranslation } from "@/lib/i18n/useTranslation";
import {
  useWishlistQuery,
  useWishlistsQuery,
  useUpdateWishlistMutation,
  useDeleteWishlistMutation,
} from "./hooks";
import {
  compressImage,
  DEFAULT_COVER_GRADIENT,
  parseWishlistDescription,
  formatWishlistDescription,
} from "./utils";
import {
  useCreateWishMutation,
  useCopyWishMutation,
  useDeleteWishMutation,
  useDeleteWishImageMutation,
  useReorderWishesMutation,
  useUpdateWishMutation,
  useUploadWishImageMutation,
  useWishesQuery,
} from "@/features/wishes/hooks";
import type { Wish } from "@/features/wishes/types";
import type { WishlistVisibility } from "./types";
import { getWishlistCoverStyle, WishImageThumb, resolveImageUrl } from "./wishlist-visuals";
import { useModalFocusMode } from "./use-modal-focus-mode";
import { ImageCropperModal } from "@/components/ui/image-cropper";
import { useProfileQuery } from "@/features/profile/hooks";
import {
  useCreateReservationMutation,
  useCancelReservationMutation,
  useReservationStatusQuery,
} from "@/features/reservations/hooks";

function formatPrice(price: string | null, currency: string | null) {
  if (!price) return "";
  const formatted = price.replace(".", ",");
  const symbol = currency || "$";
  return `${formatted} ${symbol}`;
}

function reorderIds(ids: string[], activeId: string, overId: string) {
  const from = ids.indexOf(activeId);
  const to = ids.indexOf(overId);

  if (from < 0 || to < 0 || from === to) {
    return ids;
  }

  const next = [...ids];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

type WishlistDetailManagerProps = {
  wishlistId: string;
};

type PreviewFile = File & {
  previewUrl?: string;
};

/**
 * manage wishlist details and wishes combined
 */
export function WishlistDetailManager({ wishlistId }: WishlistDetailManagerProps) {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.accessToken);
  const fallbackCover = useUIStore((state) => state.coverStyle);
  const { t } = useTranslation();
  const profileQuery = useProfileQuery(accessToken);
  const currentUserId = profileQuery.data?.id;

  // local states for editing wishlist
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [selectedCover, setSelectedCover] = useState<string>("");
  const [visibility, setVisibility] = useState<WishlistVisibility>("public");
  const [editModalOpen, setEditModalOpen] = useState(false);

  const [wishModalOpen, setWishModalOpen] = useState(false);
  const [selectedWish, setSelectedWish] = useState<Wish | null>(null);
  const [wishViewModalOpen, setWishViewModalOpen] = useState(false);
  const [editWishModalOpen, setEditWishModalOpen] = useState(false);
  
  const [wishOrderIds, setWishOrderIds] = useState<string[]>([]);
  const [activeDragWish, setActiveDragWish] = useState<Wish | null>(null);
  const isDragging = activeDragWish !== null;
  const isReordering = useIsMutating({ mutationKey: ["reorderWishes", wishlistId] }) > 0;

  // wishlist query and mutations
  const { data: wishlist, isError: wishlistError } = useWishlistQuery(wishlistId);
  const updateWishlistMutation = useUpdateWishlistMutation();
  const deleteWishlistMutation = useDeleteWishlistMutation();

  // wishes query and mutations
  const wishesQuery = useWishesQuery(wishlistId, { refetchInterval: (isDragging || isReordering) ? false : 2000 });
  const wishes = useMemo(() => wishesQuery.data?.items ?? [], [wishesQuery.data?.items]);
  const createWishMutation = useCreateWishMutation(wishlistId);
  const updateWishMutation = useUpdateWishMutation(wishlistId);
  const deleteWishMutation = useDeleteWishMutation(wishlistId);
  const uploadImageMutation = useUploadWishImageMutation(wishlistId);
  const deleteImageMutation = useDeleteWishImageMutation(wishlistId);
  const reorderWishesMutation = useReorderWishesMutation(wishlistId);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        delay: 300,
        tolerance: 6,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // prevent mobile scrolling on drag
  useEffect(() => {
    if (!activeDragWish) return;
    const preventScroll = (e: TouchEvent) => {
      e.preventDefault();
    };
    document.addEventListener("touchmove", preventScroll, { passive: false });
    return () => {
      document.removeEventListener("touchmove", preventScroll);
    };
  }, [activeDragWish]);

  // load wishlist values into edit form state
  useEffect(() => {
    if (wishlist) {
      const { description, coverStyle } = parseWishlistDescription(wishlist.description);
      setEditTitle(wishlist.title);
      setEditDesc(description ?? "");
      setSelectedCover(coverStyle);
      setVisibility(wishlist.visibility);
    }
  }, [wishlist]);

  useEffect(() => {
    if (!selectedWish) return;

    const currentWish = wishes.find((wish) => wish.id === selectedWish.id);
    if (currentWish && currentWish !== selectedWish) {
      setSelectedWish(currentWish);
    }
  }, [wishes, selectedWish]);

  useEffect(() => {
    if (activeDragWish || reorderWishesMutation.isPending || isReordering) return;
    const wishIds = wishes.map((wish) => wish.id);
    setWishOrderIds((prev) => {
      if (prev.length === wishIds.length && prev.every((id, idx) => id === wishIds[idx])) {
        return prev;
      }
      return wishIds;
    });
  }, [wishes, reorderWishesMutation.isPending, isReordering, activeDragWish]);

  const orderedWishes = useMemo(() => {
    const byId = new Map(wishes.map((wish) => [wish.id, wish]));
    return wishOrderIds.map((id) => byId.get(id)).filter((wish): wish is Wish => Boolean(wish));
  }, [wishes, wishOrderIds]);

  if (!accessToken) {
    return (
      <main className="min-h-dvh px-5 py-6">
        <p className="text-sm text-muted">{t("authenticateBeforeEditingWishes")}</p>
      </main>
    );
  }

  if (wishlistError || !wishlist) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center p-6 text-center">
        <p className="text-sm text-destructive mb-4">{t("unableToLoadWishlists")}</p>
        <Link href="/wishlists" className="text-sm font-bold text-primary underline">
          {t("backToWishlists") ?? "Back to Wishlists"}
        </Link>
      </div>
    );
  }

  const { coverStyle } = parseWishlistDescription(wishlist.description);
  const isOwner = !!currentUserId && wishlist.owner_user_id === currentUserId;

  // update wishlist settings
  function handleSaveSettings(title: string, desc: string, cover: string, vis: WishlistVisibility) {
    const cleanTitle = finalizeTextInput(title, 120);
    const cleanDescription = finalizeTextInput(desc, 1000);
    if (!cleanTitle || !cover) return;

    const formattedDesc = formatWishlistDescription(cleanDescription, cover);
    updateWishlistMutation.mutate({
      id: wishlistId,
      input: {
        title: cleanTitle,
        description: formattedDesc,
        visibility: vis,
      },
    }, {
      onSuccess: () => {
        setEditModalOpen(false);
      }
    });
  }

  // delete wishlist
  function handleDeleteWishlist() {
    deleteWishlistMutation.mutate(wishlistId, {
      onSuccess: () => {
        router.push("/wishlists");
      },
    });
  }

  // share profile to telegram
  function handleShare() {
    const username = profileQuery.data?.username;
    if (!username) return;
    const shareUrl = `${window.location.origin}/users/${encodeURIComponent(username)}`;
    const tgShareUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}`;
    const win = window as unknown as { Telegram?: { WebApp?: { openTelegramLink?: (url: string) => void } } };
    if (typeof window !== "undefined" && win.Telegram?.WebApp?.openTelegramLink) {
      win.Telegram.WebApp.openTelegramLink(tgShareUrl);
    } else {
      window.open(tgShareUrl, "_blank");
    }
  }

  // create wish
  function handleCreateWish(title: string, description: string, price: string, currency: string, imageFile?: PreviewFile) {
    setWishModalOpen(false);
    const normalizedPrice = price.trim();
    const normalizedCurrency = currency.trim();
    createWishMutation.mutate(
      {
        title,
        description: description || null,
        price: normalizedPrice && normalizedCurrency ? normalizedPrice : null,
        currency: normalizedPrice && normalizedCurrency ? normalizedCurrency : null,
      },
      {
        onSuccess: (wish) => {
          if (imageFile) {
            uploadImageMutation.mutate({ wishId: wish.id, file: imageFile, previewUrl: imageFile.previewUrl });
          }
        },
      },
    );
  }

  function handleDragStart(event: DragStartEvent) {
    const { active } = event;
    const activeItem = wishes.find((w) => w.id === active.id);
    if (activeItem) {
      setActiveDragWish(activeItem);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = wishOrderIds.indexOf(active.id as string);
      const newIndex = wishOrderIds.indexOf(over.id as string);
      const newOrder = arrayMove(wishOrderIds, oldIndex, newIndex);

      setWishOrderIds(newOrder);

      reorderWishesMutation.mutate(
        { wish_ids: newOrder },
        {
          onError: () => {
            setWishOrderIds(wishOrderIds); // revert on error
          },
        }
      );
    }
    setActiveDragWish(null);
  }

  function handleDragCancel() {
    setActiveDragWish(null);
  }

  return (
    <div className="min-h-dvh flex flex-col">
      <header
        className="cover cover-compact"
        style={getWishlistCoverStyle({ coverStyle, fallback: fallbackCover })}
      >
        <UIControls />

        <div className="flex items-end justify-between w-full mt-auto">
          <h1 className="cover-title line-clamp-1 pr-4 mt-auto">{wishlist.title}</h1>
        </div>
      </header>

      <main className="content wishlist-detail-content flex-1 flex flex-col gap-4">
        {wishesQuery.isError ? <p className="text-sm text-muted text-center py-4">{t("unableToLoadWishes")}</p> : null}

        {!wishesQuery.isError ? (
          <div className="panel flex flex-col gap-3">
            <div className="flex justify-between items-center border-b-2 border-border pb-3 mb-1">
              <h2 className="text-base font-bold text-foreground">{t("wishes") ?? "Wishes"}</h2>
              {isOwner && wishes.length > 0 && (
                <button
                  onClick={() => setWishModalOpen(true)}
                  className="pressable-link text-sm font-semibold text-primary flex items-center gap-1.5 cursor-pointer"
                >
                  <span>{t("add") ?? "Add"}</span>
                  <svg className="w-5 h-5 stroke-[2] fill-none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="9" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v8m-4-4h8" />
                  </svg>
                </button>
              )}
            </div>

            {wishesQuery.isPending || wishesQuery.isLoading ? (
              <div className="flex flex-col gap-3">
                <div className="public-skeleton h-20 w-full rounded-xl" />
                <div className="public-skeleton h-20 w-full rounded-xl" />
              </div>
            ) : wishes.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-center p-6 gap-4">
                <p className="text-sm text-muted">
                  {isOwner ? (t("noWishesDesc") ?? "Create your first wish to get started") : t("noPublicWishes")}
                </p>
                {isOwner ? (
                  <button
                    onClick={() => setWishModalOpen(true)}
                    className="pressable-action w-full flex items-center justify-center gap-2 h-12 rounded-xl border border-border bg-background text-primary font-semibold text-sm cursor-pointer"
                  >
                    <span className="text-lg leading-none">+</span>
                    <span>{t("createWishButton")}</span>
                  </button>
                ) : null}
              </div>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onDragCancel={handleDragCancel}
              >
                <div className="flex flex-col">
                  <SortableContext
                    items={wishOrderIds}
                    strategy={verticalListSortingStrategy}
                  >
                    {orderedWishes.map((wish, index) => {
                      const isLast = index === orderedWishes.length - 1;
                      return (
                        <SortableWishRow
                          key={wish.id}
                          wish={wish}
                          isOwner={isOwner}
                          isLast={isLast}
                          onClick={() => {
                            setSelectedWish(wish);
                            setWishViewModalOpen(true);
                          }}
                        />
                      );
                    })}
                  </SortableContext>
                </div>
                <DragOverlay
                  dropAnimation={{
                    sideEffects: defaultDropAnimationSideEffects({
                      styles: { active: { opacity: "0.4" } },
                    }),
                  }}
                >
                  {activeDragWish ? (
                    <WishRowOverlay wish={activeDragWish} />
                  ) : null}
                </DragOverlay>
              </DndContext>
            )}
          </div>
        ) : null}

        {isOwner ? (
          <div className="wishlist-action-bar">
            <button
              onClick={() => setEditModalOpen(true)}
              className="wishlist-action-button wishlist-action-button-secondary"
            >
              <span>{t("edit") ?? "Edit"}</span>
            </button>
            <button
              onClick={handleShare}
              className="wishlist-action-button wishlist-action-button-primary"
            >
              <span>{t("shareProfile")}</span>
            </button>
          </div>
        ) : null}
      </main>

      <CreateWishModal
        open={wishModalOpen}
        onClose={() => setWishModalOpen(false)}
        onCreate={handleCreateWish}
        isPending={createWishMutation.isPending}
      />

      <WishDetailsModal
        open={wishViewModalOpen}
        wish={selectedWish}
        wishlistId={wishlistId}
        isOwner={isOwner}
        onClose={() => {
          setWishViewModalOpen(false);
          setSelectedWish(null);
        }}
        onEdit={() => {
          setWishViewModalOpen(false);
          setEditWishModalOpen(true);
        }}
      />

      <EditWishlistModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        onSave={handleSaveSettings}
        onDelete={handleDeleteWishlist}
        isPending={updateWishlistMutation.isPending}
        initialTitle={editTitle}
        initialDescription={editDesc}
        initialCover={selectedCover}
        initialVisibility={visibility}
      />

      <EditWishModal
        open={editWishModalOpen}
        onClose={() => {
          setEditWishModalOpen(false);
          setSelectedWish(null);
        }}
        wish={selectedWish}
        onUpdate={(input) => {
          if (selectedWish) {
            updateWishMutation.mutate({ id: selectedWish.id, input });
          }
        }}
        onDelete={() => {
          if (selectedWish) {
            deleteWishMutation.mutate(selectedWish.id);
          }
        }}
        onUploadImage={(file) => {
          if (selectedWish) {
            uploadImageMutation.mutate({ wishId: selectedWish.id, file, previewUrl: file.previewUrl });
          }
        }}
        onDeleteImage={(imageId) => {
          if (selectedWish) {
            deleteImageMutation.mutate({ wishId: selectedWish.id, imageId });
          }
        }}
        isPending={updateWishMutation.isPending}
      />
    </div>
  );
}

function SortableWishRow({ wish, isOwner, isLast, onClick }: { wish: Wish; isOwner: boolean; isLast: boolean; onClick: () => void }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: wish.id, disabled: !isOwner });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "opacity-30 relative z-10" : "relative z-0"}
      {...attributes}
      {...listeners}
    >
      <WishRowBase wish={wish} isOwner={isOwner} isLast={isLast} onClick={onClick} />
    </div>
  );
}

function WishRowOverlay({ wish }: { wish: Wish }) {
  return (
    <div className="bg-background shadow-xl rounded-2xl scale-[1.02] cursor-grabbing ring-1 ring-border/50">
      <WishRowBase wish={wish} isOwner={true} isLast={true} onClick={() => {}} />
    </div>
  );
}

function WishRowBase({ wish, isOwner, isLast, onClick }: { wish: Wish; isOwner: boolean; isLast: boolean; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      onContextMenu={(event) => {
        if (isOwner) event.preventDefault();
      }}
      className={`draggable-row pressable-action flex items-center justify-between py-3 ${isOwner ? "cursor-grab" : "cursor-pointer"} ${isLast ? "" : "border-b border-border/60"}`}
    >
      <div className="flex items-center gap-3 pointer-events-none">
        <WishImageThumb
          id={wish.id}
          title={wish.title}
          imageUrl={wish.images?.[0]?.url}
          className="w-12 h-12 rounded-xl object-cover"
        />
        <div className="flex flex-col">
          <span className="font-semibold text-sm text-foreground">{wish.title}</span>
          {wish.price && (
            <span className="text-xs text-muted mt-0.5">
              {formatPrice(wish.price, wish.currency)}
            </span>
          )}
        </div>
      </div>
      <svg className="w-5 h-5 text-muted/60 pointer-events-none" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </div>
  );
}

type WishDetailsModalProps = {
  open: boolean;
  wish: Wish | null;
  wishlistId: string;
  isOwner: boolean;
  onClose: () => void;
  onEdit: () => void;
};

/**
 * view wish details
 */
function WishDetailsModal({ open, wish, wishlistId, isOwner, onClose, onEdit }: WishDetailsModalProps) {
  const { t } = useTranslation();
  const [active, setActive] = useState(false);
  const [copyModalOpen, setCopyModalOpen] = useState(false);
  const reservationStatus = useReservationStatusQuery(wish?.id ?? "");
  const createReservation = useCreateReservationMutation(wishlistId);
  const cancelReservation = useCancelReservationMutation(wishlistId);
  const copyWish = useCopyWishMutation(wishlistId);

  useEffect(() => {
    setActive(open);
  }, [open]);

  if (!open || !wish) return null;

  const status = reservationStatus.data;
  const isReserved = status?.is_reserved ?? false;
  const isMine = status?.is_mine ?? false;
  const reservationId = status?.reservation_id ?? null;

  function handleBookToggle() {
    if (isMine && reservationId) {
      cancelReservation.mutate({ reservationId, wishId: wish!.id });
    } else if (!isReserved) {
      createReservation.mutate(wish!.id);
    }
  }

  const isBusy = createReservation.isPending || cancelReservation.isPending;

  function bookButtonLabel() {
    if (createReservation.isPending) return t("reserving");
    if (cancelReservation.isPending) return t("cancellingReservation");
    if (isMine) return t("cancelReservation");
    if (isReserved) return t("wishReservedByOther");
    return t("book");
  }

  function bookButtonClass() {
    if (isMine) return "w-full h-12 rounded-xl bg-destructive text-white text-sm font-bold inline-flex items-center justify-center";
    if (isReserved) return "w-full h-12 rounded-xl bg-muted text-muted-foreground text-sm font-bold inline-flex items-center justify-center cursor-not-allowed";
    return "w-full h-12 rounded-xl bg-primary text-white text-sm font-bold inline-flex items-center justify-center";
  }

  return (
    <div
      className={`modal-backdrop ${active ? "visible" : ""}`}
      onClick={onClose}
    >
      <div
        className={`modal-sheet ${active ? "visible" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-handle" />
        <div className="flex items-center justify-between mb-4">
          <span className="w-10" />
          <h3 className="modal-title font-bold text-lg text-center text-foreground line-clamp-1">
            {wish.title}
          </h3>
          {isOwner ? (
            <button
              type="button"
              className="pressable-link w-10 h-10 inline-flex items-center justify-center rounded-xl text-primary"
              onClick={onEdit}
              aria-label={t("editWish")}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 5.5v.01M12 12v.01M12 18.5v.01" />
              </svg>
            </button>
          ) : (
            <span className="w-10" />
          )}
        </div>

        <div className="flex flex-col items-center gap-4">
          <div className="relative w-full max-w-[210px] aspect-square rounded-3xl overflow-hidden border border-border shadow-lg">
            <WishImageThumb
              id={wish.id}
              title={wish.title}
              imageUrl={wish.images?.[0]?.url}
              className="w-full h-full object-cover"
            />
          </div>

          {wish.price ? (
            <p className="text-lg font-extrabold text-primary">{formatPrice(wish.price, wish.currency)}</p>
          ) : null}

          {!isOwner && (
            <div className="w-full flex flex-col gap-2">
              <button
                type="button"
                className={bookButtonClass()}
                onClick={handleBookToggle}
                disabled={isBusy || (isReserved && !isMine)}
              >
                <span>{bookButtonLabel()}</span>
              </button>
              <button
                type="button"
                className="w-full h-12 rounded-xl border border-border bg-background text-primary text-sm font-bold inline-flex items-center justify-center"
                onClick={() => setCopyModalOpen(true)}
              >
                <span>{t("copyToMyWishlist")}</span>
              </button>
            </div>
          )}

          {wish.description ? (
            <div className="w-full rounded-2xl border border-border bg-muted/10 px-4 py-3">
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted">{t("descriptionLabel") ?? "Description"}</p>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
                {wish.description}
              </p>
            </div>
          ) : null}
        </div>
      </div>
      <CopyWishModal
        open={copyModalOpen}
        onClose={() => setCopyModalOpen(false)}
        onCopy={(targetWishlistId) => {
          copyWish.mutate(
            { wishId: wish.id, wishlistId: targetWishlistId },
            {
              onSuccess: () => setCopyModalOpen(false),
            },
          );
        }}
        isPending={copyWish.isPending}
      />
    </div>
  );
}

type CopyWishModalProps = {
  open: boolean;
  onClose: () => void;
  onCopy: (wishlistId: string) => void;
  isPending: boolean;
};

/**
 * select copy target
 */
function CopyWishModal({ open, onClose, onCopy, isPending }: CopyWishModalProps) {
  const { t } = useTranslation();
  const wishlistsQuery = useWishlistsQuery();
  const wishlists = wishlistsQuery.data?.items ?? [];
  const [active, setActive] = useState(false);

  useEffect(() => {
    setActive(open);
  }, [open]);

  if (!open) return null;

  return (
    <div className={`modal-backdrop ${active ? "visible" : ""}`} onClick={onClose}>
      <div
        className={`modal-sheet ${active ? "visible" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-handle" />
        <h3 className="modal-title font-bold text-base mb-3 text-center">
          {t("copyToMyWishlist")}
        </h3>

        {wishlistsQuery.isLoading ? (
          <p className="text-sm text-muted text-center py-4">{t("loadingWishlists")}</p>
        ) : null}

        {!wishlistsQuery.isLoading && wishlists.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center p-4 gap-3">
            <p className="text-sm text-muted">{t("createWishlistBeforeCopy")}</p>
            <Link
              href="/wishlists"
              className="w-full h-11 rounded-xl bg-primary text-white text-sm font-bold inline-flex items-center justify-center"
              onClick={onClose}
            >
              {t("createWishlistButton")}
            </Link>
          </div>
        ) : null}

        {wishlists.length > 0 ? (
          <div className="flex flex-col divide-y divide-border border-y border-border">
            {wishlists.map((wishlist) => (
              <button
                key={wishlist.id}
                type="button"
                className="flex items-center justify-between py-3 text-left"
                disabled={isPending}
                onClick={() => onCopy(wishlist.id)}
              >
                <span className="text-sm font-semibold text-foreground">{wishlist.title}</span>
                <span className="text-xs font-semibold text-primary">
                  {isPending ? t("copying") : t("copy")}
                </span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

type EditWishlistModalProps = {
  open: boolean;
  onClose: () => void;
  onSave: (title: string, description: string, cover: string, visibility: WishlistVisibility) => void;
  onDelete: () => void;
  isPending: boolean;
  initialTitle: string;
  initialDescription: string;
  initialCover: string;
  initialVisibility: WishlistVisibility;
};

/**
 * edit wishlist modal
 */
function EditWishlistModal({
  open,
  onClose,
  onSave,
  onDelete,
  isPending,
  initialTitle,
  initialDescription,
  initialCover,
  initialVisibility,
}: EditWishlistModalProps) {
  const { t } = useTranslation();
  const fallbackCover = useUIStore((state) => state.coverStyle);
  const focusMode = useModalFocusMode();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  const [selectedCover, setSelectedCover] = useState(initialCover);
  const [visibility, setVisibility] = useState<WishlistVisibility>(initialVisibility);
  const [active, setActive] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [pendingCropFile, setPendingCropFile] = useState<File | null>(null);
  const [deleteConfirming, setDeleteConfirming] = useState(false);
  const hasCustomCover = selectedCover && (selectedCover.startsWith("data:") || selectedCover.startsWith("http"));

  useEffect(() => {
    if (open) {
      setActive(true);
      setTitle(initialTitle);
      setDescription(initialDescription);
      setSelectedCover(initialCover);
      setVisibility(initialVisibility);
      setPendingCropFile(null);
      setDeleteConfirming(false);
    } else {
      setActive(false);
    }
  }, [open, initialTitle, initialDescription, initialCover, initialVisibility]);

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
    setTitle(cleanTitle);
    setDescription(cleanDescription);
    if (cleanTitle) {
      onSave(cleanTitle, cleanDescription, selectedCover, visibility);
    }
  }

  function handleCancel() {
    if (focusMode.isFocusMode) {
      focusMode.clearFocus();
      return;
    }

    onClose();
  }

  function handleDeleteCancel() {
    setDeleteConfirming(false);
  }

  function handleDeleteConfirm() {
    onDelete();
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
          {deleteConfirming
            ? (t("deleteWishlistTitle") ?? "Delete wishlist")
            : (t("editWishlist") ?? "Edit Wishlist")}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div
            className={`modal-footer-transition ${
              deleteConfirming
                ? "opacity-100 max-h-32 scale-100"
                : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
            }`}
          >
            <div className="flex flex-col items-center text-center gap-3 py-2">
              <p className="text-sm text-muted leading-6">
                {t("deleteConfirm") ?? "Are you sure you want to delete this wishlist?"}
              </p>
              <div className="flex gap-2 w-full">
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                  onClick={handleDeleteCancel}
                  disabled={isPending}
                >
                  {t("cancelButton") ?? "Cancel"}
                </button>
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-red-500 text-white h-10 text-sm font-medium transition-colors disabled:opacity-60"
                  onClick={handleDeleteConfirm}
                  disabled={isPending}
                >
                  {isPending ? (t("deleting") ?? "Deleting...") : (t("confirmDeleteButton") ?? "Delete")}
                </button>
              </div>
            </div>
          </div>

          <div
            className={`modal-footer-transition ${
              !deleteConfirming
                ? "opacity-100 max-h-[640px] scale-100"
                : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
            }`}
          >
            <div className="flex flex-col gap-4">
              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("title")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("wishlistTitleLabel")}</label>
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

              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("description")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("descriptionLabel")}</label>
                <textarea
                  className="min-h-14 max-h-20 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
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

              {/* upload cover photo section */}
              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("cover")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("coverStyle") ?? "Cover Photo"}</label>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div
                  className={hasCustomCover ? "wish-upload-cover-preview relative h-20 rounded-xl overflow-hidden border border-border text-left" : "wish-upload-cover-surface relative h-20 rounded-xl overflow-hidden cursor-pointer flex flex-col items-center justify-center gap-1 transition-all"}
                  onClick={() => fileInputRef.current?.click()}
                  style={getWishlistCoverStyle({ coverStyle: selectedCover || DEFAULT_COVER_GRADIENT, fallback: fallbackCover })}
                >
                  {hasCustomCover ? (
                    <span className="wish-upload-cover-preview-label">{t("changeCover") ?? "Change Cover"}</span>
                  ) : (
                    <span className="wish-upload-cover-label">
                      {compressing ? (t("compressing") ?? "Uploading...") : (t("uploadCover") ?? "Upload Cover")}
                    </span>
                  )}
                </div>
              </div>

              {/* horizontal privacy selector */}
              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("privacy")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("privacy") ?? "Privacy"}</label>
                <div className="flex gap-2 w-full">
                  {/* public */}
                  <button
                    type="button"
                    className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-2 rounded-2xl border transition-all ${visibility === "public"
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
                    className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-2 rounded-2xl border transition-all ${visibility === "private"
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
            </div>
          </div>

          <div className={`${deleteConfirming ? "" : "border-t border-border mt-2 pt-2"} relative overflow-hidden`}>
            <div
              className={`modal-footer-transition ${
                focusMode.isFocusMode && !deleteConfirming
                  ? "opacity-100 max-h-12 scale-100 mt-1"
                  : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
              }`}
            >
              <button
                type="button"
                className="w-full rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all"
                onClick={focusMode.clearFocus}
              >
                {t("done") ?? "Done"}
              </button>
            </div>
            <div
              className={`flex flex-col gap-2 modal-footer-transition ${
                !focusMode.isFocusMode && !deleteConfirming
                  ? "opacity-100 max-h-32 scale-100"
                  : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
              }`}
            >
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                  onClick={handleCancel}
                >
                  {t("cancelButton") ?? "Cancel"}
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all"
                  disabled={isPending || compressing}
                >
                  {isPending ? (t("saving") ?? "Saving...") : (t("saveButton") ?? "Save")}
                </button>
              </div>
              <button
                type="button"
                className={`w-full rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500/15 h-10 text-sm font-medium transition-colors mt-1`}
                onClick={() => setDeleteConfirming(true)}
              >
                {t("deleteButton") ?? "Delete Wishlist"}
              </button>
            </div>
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

type CreateWishModalProps = {
  open: boolean;
  onClose: () => void;
  onCreate: (title: string, description: string, price: string, currency: string, imageFile?: PreviewFile) => void;
  isPending: boolean;
};

/**
 * create wish modal
 */
function CreateWishModal({ open, onClose, onCreate, isPending }: CreateWishModalProps) {
  const { t } = useTranslation();
  const focusMode = useModalFocusMode();
  const [step, setStep] = useState<1 | 2>(1);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("");
  const [active, setActive] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [coverPreview, setCoverPreview] = useState("");
  const [coverFile, setCoverFile] = useState<PreviewFile | undefined>();
  const [pendingCropFile, setPendingCropFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setActive(true);
      setStep(1);
      setTitle("");
      setDescription("");
      setPrice("");
      setCurrency("");
      setCoverPreview("");
      setCoverFile(undefined);
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
    const cleanTitle = finalizeTextInput(title, 160);
    const cleanDescription = finalizeTextInput(description, 2000);
    const cleanPrice = finalizePriceInput(price);
    const cleanCurrency = normalizeCurrencyInput(currency);

    if (step === 1) {
      setTitle(cleanTitle);
      setPrice(cleanPrice);
      setCurrency(cleanCurrency);
      if (cleanTitle) {
        setStep(2);
      }
      return;
    }

    setDescription(cleanDescription);
    onCreate(cleanTitle, cleanDescription, cleanPrice, cleanCurrency, coverFile);
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
          {step === 1 ? (t("createNewWish") ?? "Create New Wish") : (t("configureWish") ?? "Add Details")}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="public-nav-viewport" style={{ maxHeight: "none", overflow: "visible", padding: 0 }}>
            {step === 1 ? (
              <div
                key="wish-info-step"
                className="public-nav-frame public-nav-enter-back flex flex-col gap-3"
              >
                <div className={`flex flex-col gap-1 ${focusMode.sectionClass("title")}`}>
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("wishTitleLabel") ?? "Wish Title"}</label>
                  <input
                    type="text"
                    required
                    className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    value={title}
                    onBlur={() => {
                      setTitle((current) => finalizeTextInput(current, 160));
                      focusMode.onFieldBlur();
                    }}
                    onChange={(e) => setTitle(normalizeTextInput(e.currentTarget.value, 160))}
                    maxLength={160}
                    {...focusMode.fieldFocusProps("title")}
                  />
                </div>

                <div className={`grid grid-cols-2 gap-2 ${focusMode.sectionClass("details")}`}>
                  <div className="flex flex-col gap-1 col-span-1">
                    <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("priceLabel") ?? "Price"}</label>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                      value={price}
                      onBlur={() => {
                        setPrice((current) => finalizePriceInput(current));
                        focusMode.onFieldBlur();
                      }}
                      onChange={(e) => setPrice(normalizePriceInput(e.currentTarget.value))}
                      {...focusMode.fieldFocusProps("details")}
                    />
                  </div>

                  <div className="flex flex-col gap-1 col-span-1">
                    <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("currencyLabel") ?? "Currency"}</label>
                    <input
                      type="text"
                      maxLength={3}
                      className="h-11 rounded-xl border border-border bg-background px-3 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary/50"
                      value={currency}
                      onChange={(e) => setCurrency(normalizeCurrencyInput(e.currentTarget.value))}
                      {...focusMode.fieldFocusProps("details")}
                      onBlur={focusMode.onFieldBlur}
                    />
                  </div>
                </div>

                <div className="border-t border-border mt-2 pt-2 relative overflow-hidden">
                  <div
                    className={`modal-footer-transition ${
                      focusMode.isFocusMode
                        ? "opacity-100 max-h-12 scale-100 mt-1"
                        : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
                    }`}
                  >
                    <button
                      type="button"
                      className="w-full rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all"
                      onClick={focusMode.clearFocus}
                    >
                      {t("done") ?? "Done"}
                    </button>
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
                    <button
                      type="submit"
                      className="flex-1 rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      disabled={!title.trim()}
                    >
                      {t("next") ?? "Next"}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div
                key="wish-media-step"
                className="public-nav-frame public-nav-enter-forward flex flex-col gap-3"
              >
                <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("photo")}`}>
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("imagesLabel") ?? "Photo"}</label>
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="image/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <div
                    className={coverPreview ? "wish-upload-cover-preview relative h-20 rounded-xl overflow-hidden border border-border text-left" : "wish-upload-cover-surface relative h-20 rounded-xl overflow-hidden cursor-pointer flex flex-col items-center justify-center gap-1 transition-all"}
                    onClick={() => fileInputRef.current?.click()}
                    style={coverPreview ? { backgroundImage: `url(${coverPreview})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}
                  >
                    <span className={coverPreview ? "wish-upload-cover-preview-label" : "wish-upload-cover-label"}>
                      {compressing ? (t("compressing") ?? "Uploading...") : coverPreview ? (t("changeCover") ?? "Change Cover") : (t("uploadCover") ?? "Upload Cover")}
                    </span>
                  </div>
                </div>

                <div className={`flex flex-col gap-1 ${focusMode.sectionClass("description")}`}>
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider mb-1">{t("descriptionLabel") ?? "Description"}</label>
                  <textarea
                    className="min-h-16 max-h-24 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                    value={description}
                    onBlur={() => {
                      setDescription((current) => finalizeTextInput(current, 2000));
                      focusMode.onFieldBlur();
                    }}
                    onChange={(event) => setDescription(normalizeTextInput(event.currentTarget.value, 2000))}
                    maxLength={2000}
                    {...focusMode.fieldFocusProps("description")}
                  />
                </div>

                <div className="flex gap-2 mt-2">
                  <button
                    type="button"
                    className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                    onClick={() => setStep(1)}
                  >
                    {t("back") ?? "Back"}
                  </button>
                  <button
                    type="submit"
                    className="flex-1 rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={isPending || compressing}
                  >
                    {isPending ? (t("creating") ?? "Creating...") : (t("createWishButton") ?? "Create")}
                  </button>
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
              const res = await fetch(dataUrl);
              const blob = await res.blob();
              setCoverPreview(dataUrl);
              setCoverFile(Object.assign(new File([blob], croppedFile.name, { type: croppedFile.type }), { previewUrl: dataUrl }));
            } catch (err) {
              console.error("Image upload failed", err);
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

type EditWishModalProps = {
  open: boolean;
  onClose: () => void;
  wish: Wish | null;
  onUpdate: (input: { title?: string; description?: string | null; price?: string | null; currency?: string | null }) => void;
  onDelete: () => void;
  onUploadImage: (file: PreviewFile) => void;
  onDeleteImage: (imageId: string) => void;
  isPending: boolean;
};

/**
 * edit wish modal
 */
function EditWishModal({
  open,
  onClose,
  wish,
  onUpdate,
  onDelete,
  onUploadImage,
  isPending,
}: EditWishModalProps) {
  const { t } = useTranslation();
  const focusMode = useModalFocusMode();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("");
  const [active, setActive] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [pendingCropFile, setPendingCropFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [localCoverPreview, setLocalCoverPreview] = useState<string | null>(null);
  const [deleteConfirming, setDeleteConfirming] = useState(false);

  useEffect(() => {
    if (open && wish) {
      setActive(true);
      setTitle(wish.title ?? "");
      setDescription(wish.description ?? "");
      setPrice(wish.price ?? "");
      setCurrency(wish.currency ?? "");
      if (!localCoverPreview) {
        setLocalCoverPreview(wish.images?.[0]?.url ?? null);
      }
      setPendingCropFile(null);
      setDeleteConfirming(false);
    } else {
      setActive(false);
      setLocalCoverPreview(null);
    }
  }, [open, wish]);

  if (!open || !wish) return null;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingCropFile(file);
    e.target.value = "";
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleanTitle = finalizeTextInput(title, 160);
    const cleanDescription = finalizeTextInput(description, 2000);
    const cleanPrice = finalizePriceInput(price);
    const cleanCurrency = normalizeCurrencyInput(currency);
    setTitle(cleanTitle);
    setDescription(cleanDescription);
    setPrice(cleanPrice);
    setCurrency(cleanCurrency);
    if (cleanTitle) {
      onUpdate({
        title: cleanTitle,
        description: cleanDescription || null,
        price: cleanPrice && cleanCurrency ? cleanPrice : null,
        currency: cleanPrice && cleanCurrency ? cleanCurrency : null,
      });
      onClose();
    }
  }

  function handleCancel() {
    if (focusMode.isFocusMode) {
      focusMode.clearFocus();
      return;
    }

    onClose();
  }

  function handleDeleteCancel() {
    setDeleteConfirming(false);
  }

  function handleDeleteConfirm() {
    onDelete();
    onClose();
  }

  const hasImage = wish.images && wish.images.length > 0;

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
          {deleteConfirming
            ? (t("deleteWishTitle") ?? "Delete wish")
            : (t("editWish") ?? "Edit Wish")}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div
            className={`modal-footer-transition ${
              deleteConfirming
                ? "opacity-100 max-h-32 scale-100"
                : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
            }`}
          >
            <div className="flex flex-col items-center text-center gap-3 py-2">
              <p className="text-sm text-muted leading-6">
                {t("deleteWishConfirm") ?? "Are you sure you want to delete this wish?"}
              </p>
              <div className="flex gap-2 w-full">
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                  onClick={handleDeleteCancel}
                  disabled={isPending}
                >
                  {t("cancelButton") ?? "Cancel"}
                </button>
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-red-500 text-white h-10 text-sm font-medium transition-colors disabled:opacity-60"
                  onClick={handleDeleteConfirm}
                  disabled={isPending}
                >
                  {isPending ? (t("deleting") ?? "Deleting...") : (t("confirmDeleteButton") ?? "Delete")}
                </button>
              </div>
            </div>
          </div>

          <div
            className={`modal-footer-transition ${
              !deleteConfirming
                ? "opacity-100 max-h-[760px] scale-100"
                : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
            }`}
          >
            <div className="flex flex-col gap-4">
              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("title")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("wishTitleLabel") ?? "Wish Title"}</label>
                <input
                  type="text"
                  required
                  className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                  value={title}
                  onBlur={() => {
                    setTitle((current) => finalizeTextInput(current, 160));
                    focusMode.onFieldBlur();
                  }}
                  onChange={(e) => setTitle(normalizeTextInput(e.currentTarget.value, 160))}
                  maxLength={160}
                  {...focusMode.fieldFocusProps("title")}
                />
              </div>

              <div className={`grid grid-cols-2 gap-2 ${focusMode.sectionClass("details")}`}>
                <div className="flex flex-col gap-1.5 col-span-1">
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("priceLabel") ?? "Price"}</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="h-11 rounded-xl border border-border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    value={price}
                    onBlur={() => {
                      setPrice((current) => finalizePriceInput(current));
                      focusMode.onFieldBlur();
                    }}
                    onChange={(e) => setPrice(normalizePriceInput(e.currentTarget.value))}
                    {...focusMode.fieldFocusProps("details")}
                  />
                </div>

                <div className="flex flex-col gap-1.5 col-span-1">
                  <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("currencyLabel") ?? "Currency"}</label>
                  <input
                    type="text"
                    maxLength={3}
                    className="h-11 rounded-xl border border-border bg-background px-3 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-primary/50"
                    value={currency}
                    onChange={(e) => setCurrency(normalizeCurrencyInput(e.currentTarget.value))}
                    {...focusMode.fieldFocusProps("details")}
                    onBlur={focusMode.onFieldBlur}
                  />
                </div>
              </div>

              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("description")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("descriptionLabel") ?? "Description"}</label>
                <textarea
                  className="min-h-16 max-h-24 rounded-xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                  value={description}
                  onBlur={() => {
                    setDescription((current) => finalizeTextInput(current, 2000));
                    focusMode.onFieldBlur();
                  }}
                  onChange={(event) => setDescription(normalizeTextInput(event.currentTarget.value, 2000))}
                  maxLength={2000}
                  {...focusMode.fieldFocusProps("description")}
                />
              </div>

              {/* photo upload */}
              <div className={`flex flex-col gap-1.5 ${focusMode.sectionClass("photo")}`}>
                <label className="text-[10px] font-extrabold text-muted uppercase tracking-wider">{t("imagesLabel") ?? "Photo"}</label>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                {localCoverPreview ? (
                  <div
                    className="wish-upload-cover-preview relative h-20 rounded-xl overflow-hidden border border-border text-left"
                    onClick={() => fileInputRef.current?.click()}
                    style={{ backgroundImage: `url(${resolveImageUrl(localCoverPreview)})`, backgroundSize: "cover", backgroundPosition: "center" }}
                  >
                    <span className="wish-upload-cover-preview-label">
                      {compressing ? (t("compressing") ?? "Uploading...") : (t("changeCover") ?? "Change cover")}
                    </span>
                  </div>
                ) : (
                  <div
                    className="wish-upload-cover-surface relative h-20 rounded-xl overflow-hidden cursor-pointer flex flex-col items-center justify-center gap-1 transition-all"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <span className="wish-upload-cover-label">
                      {compressing ? (t("compressing") ?? "Uploading...") : (t("uploadCover") ?? "Upload Cover")}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>


          <div className={`${deleteConfirming ? "" : "border-t border-border mt-2 pt-2"} relative overflow-hidden`}>
            <div
              className={`modal-footer-transition ${
                focusMode.isFocusMode && !deleteConfirming
                  ? "opacity-100 max-h-12 scale-100 mt-1"
                  : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
              }`}
            >
              <button
                type="button"
                className="w-full rounded-xl bg-primary text-white h-10 text-sm font-medium hover:bg-primary/95 transition-all"
                onClick={focusMode.clearFocus}
              >
                {t("done") ?? "Done"}
              </button>
            </div>
            <div
              className={`flex flex-col gap-2 modal-footer-transition ${
                !focusMode.isFocusMode && !deleteConfirming
                  ? "opacity-100 max-h-32 scale-100"
                  : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
              }`}
            >
              <div className="flex gap-2">
                <button
                  type="button"
                  className="flex-1 rounded-xl bg-muted/10 hover:bg-muted/20 text-muted h-10 text-sm font-medium transition-colors"
                  onClick={handleCancel}
                >
                  {t("cancelButton") ?? "Cancel"}
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-primary hover:bg-primary/90 text-white h-10 text-sm font-medium transition-all"
                  disabled={isPending || compressing}
                >
                  {isPending ? (t("saving") ?? "Saving...") : (t("saveButton") ?? "Save")}
                </button>
              </div>
              <button
                type="button"
                className={`w-full rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500/15 h-10 text-sm font-medium transition-colors mt-1`}
                onClick={() => setDeleteConfirming(true)}
              >
                {t("deleteButton") ?? "Delete Wish"}
              </button>
            </div>
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
              const res = await fetch(dataUrl);
              const blob = await res.blob();
              const newFile = Object.assign(new File([blob], croppedFile.name, { type: croppedFile.type }), { previewUrl: dataUrl });
              setLocalCoverPreview(dataUrl);
              onUploadImage(newFile);
            } catch (err) {
              console.error("Image upload failed", err);
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
