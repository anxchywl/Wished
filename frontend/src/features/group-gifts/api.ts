// group gifts api client
import { apiClient } from "@/lib/api";

export interface ContributionSummary {
  id: string;
  amount: string;
  status: string;
  created_at: string;
}

export interface GroupGiftMemberSummary {
  user_id: string;
  contribution_id: string | null;
  role: "organizer" | "contributor";
  first_name: string | null;
  username: string | null;
  amount: string | null;
  status: string | null;
  created_at: string | null;
}

export interface GroupGiftSummary {
  id: string;
  status: string;
  collection_type: string;
  collected_amount: string;
  remaining_amount: string | null;
  percent_complete: number;
  contributor_count: number;
  is_organizer: boolean;
  is_contributor: boolean;
}

export interface GroupGiftResponse {
  id: string;
  wish_id: string;
  collection_type: string;
  status: string;
  payment_method: string | null;
  payment_phone: string | null;
  payment_comment: string | null;
  total_amount: string | null;
  collected_amount: string;
  remaining_amount: string | null;
  percent_complete: number;
  contributor_count: number;
  is_organizer: boolean;
  is_contributor: boolean;
  my_contribution: ContributionSummary | null;
  organizer_display_name: string | null;
  created_at: string;
}

export interface GroupGiftCreatePayload {
  collection_type: "immediate" | "commit";
  payment_method: string;
  payment_phone: string;
  payment_comment?: string;
}

export interface GroupGiftPaymentDetailsPayload {
  payment_method: string;
  payment_phone: string;
  payment_comment?: string;
}

export function createGroupGift(
  accessToken: string | null,
  wishId: string,
  payload: GroupGiftCreatePayload,
): Promise<GroupGiftResponse> {
  return apiClient<GroupGiftResponse>(`/wishes/${wishId}/group-gift`, {
    method: "POST",
    body: payload,
    accessToken,
  });
}

export function getGroupGift(
  accessToken: string | null,
  wishId: string,
  shareToken?: string | null,
): Promise<GroupGiftResponse | null> {
  const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : "";
  return apiClient<GroupGiftResponse | null>(`/wishes/${wishId}/group-gift${query}`, { accessToken });
}

export function cancelGroupGift(
  accessToken: string | null,
  groupGiftId: string,
): Promise<void> {
  return apiClient<null>(`/group-gifts/${groupGiftId}`, {
    method: "DELETE",
    accessToken,
  }).then(() => undefined);
}

export function updateGroupGiftPaymentDetails(
  accessToken: string | null,
  groupGiftId: string,
  payload: GroupGiftPaymentDetailsPayload,
): Promise<GroupGiftResponse> {
  return apiClient<GroupGiftResponse>(`/group-gifts/${groupGiftId}/payment-details`, {
    method: "PATCH",
    body: payload,
    accessToken,
  });
}

export function markGroupGiftPurchased(
  accessToken: string | null,
  groupGiftId: string,
): Promise<GroupGiftResponse> {
  return apiClient<GroupGiftResponse>(`/group-gifts/${groupGiftId}/purchase`, {
    method: "POST",
    accessToken,
  });
}

export function joinGroupGift(
  accessToken: string | null,
  groupGiftId: string,
  amount: number,
): Promise<ContributionSummary> {
  return apiClient<ContributionSummary>(`/group-gifts/${groupGiftId}/join`, {
    method: "POST",
    body: { amount },
    accessToken,
  });
}

export function reportTransfer(
  accessToken: string | null,
  contributionId: string,
): Promise<ContributionSummary> {
  return apiClient<ContributionSummary>(`/contributions/${contributionId}/transfer`, {
    method: "POST",
    accessToken,
  });
}

export function confirmTransfer(
  accessToken: string | null,
  contributionId: string,
  confirmed: boolean,
): Promise<ContributionSummary> {
  return apiClient<ContributionSummary>(`/contributions/${contributionId}/confirm`, {
    method: "POST",
    body: { confirmed },
    accessToken,
  });
}

export function leaveGroupGift(
  accessToken: string | null,
  contributionId: string,
): Promise<void> {
  return apiClient<null>(`/contributions/${contributionId}`, {
    method: "DELETE",
    accessToken,
  }).then(() => undefined);
}

export function organizerRemoveContribution(
  accessToken: string | null,
  groupGiftId: string,
  contributionId: string,
): Promise<void> {
  return apiClient<null>(`/group-gifts/${groupGiftId}/contributions/${contributionId}`, {
    method: "DELETE",
    accessToken,
  }).then(() => undefined);
}

export function getGiftMembers(
  accessToken: string | null,
  groupGiftId: string,
): Promise<GroupGiftMemberSummary[]> {
  return apiClient<GroupGiftMemberSummary[]>(`/group-gifts/${groupGiftId}/members`, { accessToken });
}
