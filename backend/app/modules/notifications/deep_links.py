from uuid import UUID


def profile_url(mini_app_url: str, username: str) -> str:
    """deep link to a user profile in the mini app"""
    return f"{mini_app_url}/users?profile={username}"


def wishlist_url(mini_app_url: str, wishlist_id: UUID | str) -> str:
    """deep link to a wishlist in the mini app"""
    return f"{mini_app_url}/wishlists/{wishlist_id}"


def wish_url(mini_app_url: str, wishlist_id: UUID | str, wish_id: UUID | str) -> str:
    """deep link to a wish within a wishlist in the mini app"""
    return f"{mini_app_url}/wishlists/{wishlist_id}?wish={wish_id}"
