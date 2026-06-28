from uuid import UUID


def profile_url(mini_app_url: str, username: str) -> str:
    """deep link to a user profile in the mini app"""
    return f"{mini_app_url}/users?profile={username}"


def profile_url_by_id(mini_app_url: str, user_id: UUID | str) -> str:
    """deep link to a user profile using internal UUID"""
    return f"{mini_app_url}/users?profile_id={user_id}"


def wishlist_url(mini_app_url: str, username: str, wishlist_id: UUID | str) -> str:
    """deep link that opens the profile then navigates into the wishlist"""
    return f"{mini_app_url}/users?profile={username}&wishlist={wishlist_id}"


def wishlist_url_by_id(mini_app_url: str, user_id: UUID | str, wishlist_id: UUID | str) -> str:
    """deep link that opens the profile by UUID then navigates into the wishlist"""
    return f"{mini_app_url}/users?profile_id={user_id}&wishlist={wishlist_id}"


def wish_url(mini_app_url: str, username: str, wishlist_id: UUID | str, wish_id: UUID | str) -> str:
    """deep link that opens the profile then navigates to the specific wish"""
    return f"{mini_app_url}/users?profile={username}&wishlist={wishlist_id}&wish={wish_id}"


def wish_url_by_id(
    mini_app_url: str, user_id: UUID | str, wishlist_id: UUID | str, wish_id: UUID | str
) -> str:
    """deep link that opens the profile by UUID then navigates to the specific wish"""
    return f"{mini_app_url}/users?profile_id={user_id}&wishlist={wishlist_id}&wish={wish_id}"
