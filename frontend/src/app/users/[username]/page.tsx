import { UserProfileManager } from "@/features/users";

export const dynamic = "force-dynamic";

type UsersProfilePageProps = {
  params: Promise<{
    username: string;
  }>;
};

/**
 * render user profile page
 */
export default async function UsersProfilePage({ params }: UsersProfilePageProps) {
  const { username } = await params;
  return <UserProfileManager username={username} />;
}
