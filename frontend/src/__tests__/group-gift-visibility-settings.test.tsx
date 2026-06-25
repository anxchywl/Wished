import { fireEvent, render, screen, within } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BookingVisibilityHeaderButton } from "@/features/users/user-discovery-manager";

const mutate = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/stores/auth-store", () => ({
  isAuthFailure: () => false,
  isAuthPending: () => false,
  useAuthStore: (selector: (state: { accessToken: string; authStatus: string }) => unknown) =>
    selector({ accessToken: "access-token", authStatus: "authenticated" }),
}));

vi.mock("@/features/profile/hooks", () => ({
  useProfileQuery: () => ({
    data: {
      privacy: {
        booking_visibility: "hide",
        group_gift_visibility: "anonymous",
      },
    },
  }),
  useUpdatePrivacyMutation: () => ({
    isPending: false,
    mutate,
  }),
}));

vi.mock("@/features/users/hooks", () => ({
  useFollowingQuery: () => ({ data: { items: [] }, isLoading: false }),
}));

vi.mock("@/features/reservations/hooks", () => ({
  useBookedWishesQuery: () => ({ data: { items: [] } }),
  useCancelReservationMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/lib/debug/startup-log", () => ({
  logStartup: vi.fn(),
}));

describe("BookingVisibilityHeaderButton", () => {
  beforeEach(() => {
    mutate.mockClear();
  });

  it("renders group gift visibility settings after booking settings", () => {
    render(React.createElement(BookingVisibilityHeaderButton));

    fireEvent.click(screen.getByLabelText("Booking visibility"));

    expect(screen.getByText("Booked Wishes")).toBeInTheDocument();
    expect(screen.getByText("Group Gifts")).toBeInTheDocument();
    expect(screen.getByText("Do not show group gifts on your wishes")).toBeInTheDocument();
    expect(screen.getByText("Show progress and contributor count, but not names")).toBeInTheDocument();
    expect(screen.getByText("Show who organized the gift")).toBeInTheDocument();
  });

  it("updates group_gift_visibility through the existing privacy mutation", () => {
    render(React.createElement(BookingVisibilityHeaderButton));

    fireEvent.click(screen.getByLabelText("Booking visibility"));
    const groupGiftOption = screen.getByText("Show who organized the gift").closest("button");

    expect(groupGiftOption).not.toBeNull();
    fireEvent.click(groupGiftOption!);

    expect(mutate).toHaveBeenCalledWith(
      { group_gift_visibility: "names" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });

  it("keeps booking and group gift controls independent", () => {
    render(React.createElement(BookingVisibilityHeaderButton));

    fireEvent.click(screen.getByLabelText("Booking visibility"));
    const sheet = screen.getByText("Group Gifts").closest(".modal-sheet");

    expect(sheet).not.toBeNull();
    const bookingHide = within(sheet as HTMLElement).getAllByText("Hide")[0].closest("button");
    const groupGiftHide = within(sheet as HTMLElement).getAllByText("Hide")[1].closest("button");

    fireEvent.click(bookingHide!);
    fireEvent.click(groupGiftHide!);

    expect(mutate).toHaveBeenNthCalledWith(
      1,
      { booking_visibility: "hide" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    expect(mutate).toHaveBeenNthCalledWith(
      2,
      { group_gift_visibility: "hide" },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
  });
});
