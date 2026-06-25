"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient, useIsMutating } from "@tanstack/react-query";
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
import {
  useCreateWishlistMutation,
  useReorderWishlistsMutation,
  useUploadWishlistCoverMutation,
  useWishlistsQuery,
} from "@/features/wishlists/hooks";
import { CreateWishlistModal } from "@/features/wishlists/create-wishlist-modal";
import { formatWishlistDescription } from "@/features/wishlists/utils";
import type { Wishlist, WishlistVisibility } from "@/features/wishlists/types";
import { isAuthFailure, isAuthPending, useAuthStore } from "@/stores/auth-store";
import { useTranslation } from "@/lib/i18n/useTranslation";
import { logStartup } from "@/lib/debug/startup-log";
import { finalizeTextInput } from "@/lib/forms/input-normalize";
import { AuthRequiredPanel } from "@/components/feedback/auth-required-panel";
import { getWishlist } from "@/features/wishlists/api";
import { wishlistQueryKeys } from "@/features/wishlists/query-keys";
import { listWishes } from "@/features/wishes/api";
import { wishQueryKeys } from "@/features/wishes/query-keys";
import { useWishesQuery } from "@/features/wishes/hooks";

/**
 * manage wishlists list and creation modal
 */
export function WishlistManager() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const authStatus = useAuthStore((state) => state.authStatus);
  const { t } = useTranslation();

  const [modalOpen, setModalOpen] = useState(false);
  const [wishlistOrderIds, setWishlistOrderIds] = useState<string[]>([]);
  const [activeWishlist, setActiveWishlist] = useState<Wishlist | null>(null);
  const isDragging = activeWishlist !== null;
  const isReordering = useIsMutating({ mutationKey: ["reorderWishlists"] }) > 0;

  const wishlistsQuery = useWishlistsQuery();
  const createMutation = useCreateWishlistMutation();
  const uploadCoverMutation = useUploadWishlistCoverMutation();
  const reorderMutation = useReorderWishlistsMutation();

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
    if (!activeWishlist) return;
    const preventScroll = (e: TouchEvent) => {
      e.preventDefault();
    };
    document.addEventListener("touchmove", preventScroll, { passive: false });
    return () => {
      document.removeEventListener("touchmove", preventScroll);
    };
  }, [activeWishlist]);

  function handleCreateWishlist(
    title: string,
    description: string | null,
    coverFile: File | null,
    visibility: WishlistVisibility
  ) {
    const cleanTitle = finalizeTextInput(title, 120);
    const cleanDescription = description ? finalizeTextInput(description, 1000) : null;
    const formattedDesc = formatWishlistDescription(cleanDescription);
    createMutation.mutate(
      {
        title: cleanTitle,
        description: formattedDesc || null,
        visibility,
      },
      {
        onSuccess: (wishlist) => {
          setModalOpen(false);
          if (coverFile) {
            uploadCoverMutation.mutate({ wishlistId: wishlist.id, file: coverFile });
          }
        },
      }
    );
  }

  const wishlists = useMemo(() => wishlistsQuery.data?.items ?? [], [wishlistsQuery.data?.items]);

  const resolvedOrderIds = useMemo(() => {
    if (wishlistOrderIds.length === 0) {
      return wishlists.map((wishlist) => wishlist.id);
    }
    return wishlistOrderIds;
  }, [wishlists, wishlistOrderIds]);

  // Derive ordered wishlists
  const orderedWishlists = useMemo(() => {
    const map = new Map(wishlists.map((w) => [w.id, w]));
    const ordered = resolvedOrderIds
      .map((id) => map.get(id))
      .filter((w): w is Wishlist => w !== undefined);
    const orderedIds = new Set(ordered.map((wishlist) => wishlist.id));
    return [...ordered, ...wishlists.filter((wishlist) => !orderedIds.has(wishlist.id))];
  }, [wishlists, resolvedOrderIds]);

  const hasWishlists = wishlists.length > 0;
  const querySettled = wishlistsQuery.isSuccess || wishlistsQuery.isError;
  const showWishlistsEmpty = querySettled && !wishlistsQuery.isError && !hasWishlists;
  // hold in startup until auth AND initial wishlist fetch are both done so the
  // panel and its content appear together rather than popping in after the shell
  const guardDecision = isAuthPending(authStatus) || (!querySettled && !wishlistsQuery.isError)
    ? "startup"
    : isAuthFailure(authStatus) || (authStatus !== "authenticated" && !accessToken)
      ? "auth_required"
      : "app";

  logStartup("route guard decision", authStatus, {
    component: "WishlistManager",
    decision: guardDecision,
    hasAccessToken: Boolean(accessToken),
  });

  useEffect(() => {
    if (activeWishlist || reorderMutation.isPending || isReordering) return;
    const wishlistIds = wishlists.map((wishlist) => wishlist.id);
    setWishlistOrderIds((prev) => {
      if (prev.length === wishlistIds.length && prev.every((id, idx) => id === wishlistIds[idx])) {
        return prev;
      }
      return wishlistIds;
    });
  }, [wishlists, reorderMutation.isPending, isReordering, activeWishlist]);

  function handleDragStart(event: DragStartEvent) {
    const { active } = event;
    const activeItem = wishlists.find((w) => w.id === active.id);
    if (activeItem) {
      setActiveWishlist(activeItem);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const currentOrder = wishlistOrderIds.length > 0 ? wishlistOrderIds : resolvedOrderIds;
      const oldIndex = currentOrder.indexOf(active.id as string);
      const newIndex = currentOrder.indexOf(over.id as string);
      const newOrder = arrayMove(currentOrder, oldIndex, newIndex);

      setWishlistOrderIds(newOrder);

      reorderMutation.mutate(
        { wishlist_ids: newOrder },
        {
          onError: () => {
            setWishlistOrderIds(wishlistOrderIds); // revert on error
          },
        }
      );
    }
    setActiveWishlist(null);
  }

  function handleDragCancel() {
    setActiveWishlist(null);
  }

  return (
    <>
      <main className="content flex flex-col gap-4">
        {guardDecision === "startup" ? (
          <AuthRequiredPanel forcePending />
        ) : guardDecision === "auth_required" ? (
          <AuthRequiredPanel />
        ) : (
          <>
            {wishlistsQuery.isError && (
              <p className="text-sm text-destructive text-center py-4">{t("unableToLoadWishlists")}</p>
            )}

            {showWishlistsEmpty ? (
              <div className="panel empty-state-panel flex flex-col items-center justify-center text-center p-6 gap-4">
                <p className="empty-state-desc text-sm text-muted">{t("noWishlistsDesc") ?? "Create your first wishlist to get started"}</p>
                <button
                  onClick={() => setModalOpen(true)}
                  className="pressable-action w-full flex items-center justify-center gap-2 h-12 rounded-xl border border-border bg-background text-primary font-semibold text-sm cursor-pointer"
                >
                  <svg className="w-4 h-4 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>{t("createWishlistButton")}</span>
                </button>
              </div>
            ) : null}

            {hasWishlists ? (
              <div className="panel flex flex-col p-0 overflow-hidden bg-background" style={{ padding: 0 }}>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                  onDragCancel={handleDragCancel}
                >
                  <div className="divide-y divide-border">
                    <SortableContext
                      items={resolvedOrderIds}
                      strategy={verticalListSortingStrategy}
                    >
                      {orderedWishlists.map((wishlist) => (
                        <SortableWishlistRow
                          key={wishlist.id}
                          wishlist={wishlist}
                        />
                      ))}
                    </SortableContext>
                  </div>
                  <DragOverlay
                    dropAnimation={{
                      sideEffects: defaultDropAnimationSideEffects({
                        styles: { active: { opacity: "0.4" } },
                      }),
                    }}
                  >
                    {activeWishlist ? (
                      <WishlistRowOverlay wishlist={activeWishlist} />
                    ) : null}
                  </DragOverlay>
                </DndContext>
                <button
                  onClick={() => setModalOpen(true)}
                  className="pressable-action flex items-center justify-center gap-2 p-4 w-full text-primary font-semibold text-sm cursor-pointer border-t-2 border-border"
                >
                  <svg className="w-4 h-4 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>{t("createWishlistButton")}</span>
                </button>
              </div>
            ) : null}
          </>
        )}
      </main>

      <CreateWishlistModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={handleCreateWishlist}
        isPending={createMutation.isPending}
      />
    </>
  );
}

/**
 * sortable wishlist item wrapper
 */
function SortableWishlistRow({ wishlist }: { wishlist: Wishlist }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: wishlist.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={isDragging ? "opacity-30" : ""}
      {...attributes}
      {...listeners}
    >
      <WishlistRowBase wishlist={wishlist} />
    </div>
  );
}

/**
 * drag overlay static row
 */
function WishlistRowOverlay({ wishlist }: { wishlist: Wishlist }) {
  return (
    <div className="bg-background shadow-xl rounded-2xl scale-[1.02] cursor-grabbing ring-1 ring-border/50">
      <WishlistRowBase wishlist={wishlist} />
    </div>
  );
}

/**
 * wishlist item presentation
 */
function WishlistRowBase({ wishlist }: { wishlist: Wishlist }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const router = useRouter();
  const { t } = useTranslation();

  const wishesQuery = useWishesQuery(wishlist.id, false);
  const wishesCount = wishesQuery.data?.items.length ?? 0;

  const countText = wishesQuery.data === undefined
    ? "..."
    : wishesCount === 0
      ? (t("noWishes") ?? "No wishes")
      : wishesCount === 1
        ? `1 ${t("wishCountLabel") ?? "wish"}`
        : `${wishesCount} ${t("wishesCountLabel") ?? "wishes"}`;

  function prefetchWishlist() {
    queryClient.setQueryData([...wishlistQueryKeys.detail(wishlist.id), accessToken] as const, wishlist);

    if (!accessToken) return;

    queryClient.prefetchQuery({
      queryKey: [...wishlistQueryKeys.detail(wishlist.id), accessToken] as const,
      queryFn: () => getWishlist(accessToken, wishlist.id),
    });
    queryClient.prefetchQuery({
      queryKey: wishQueryKeys.list(wishlist.id),
      queryFn: () => listWishes(accessToken, wishlist.id),
    });
  }

  function openWishlist() {
    router.push(`/wishlists/${wishlist.id}`);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWishlist();
    }
  }

  return (
    <div
      aria-label={wishlist.title}
      data-wishlist-id={wishlist.id}
      onContextMenu={(event) => event.preventDefault()}
      onFocus={prefetchWishlist}
      onKeyDown={handleKeyDown}
      onMouseEnter={prefetchWishlist}
      onClick={openWishlist}
      role="link"
      tabIndex={0}
      className={`draggable-row flex items-center justify-between p-4 transition-transform active:scale-[0.99] cursor-grab`}
    >
      <div className="flex flex-col gap-1">
        <span className="font-semibold text-sm text-foreground">{wishlist.title}</span>
        <div className="flex items-center gap-1.5 text-xs text-muted">
          {wishlist.visibility === "public" && (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          )}
          {wishlist.visibility === "private" && (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          )}
          <span>{t(wishlist.visibility) ?? wishlist.visibility}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 text-primary font-medium text-xs pointer-events-none">
        <span>{countText}</span>
        <svg className="w-3.5 h-3.5 text-muted/60" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}
