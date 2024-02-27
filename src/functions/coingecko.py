import requests;

COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

def coin_price_usd(coin: str) -> dict:
    """Get the up to date USD price of a cryptocurrency from CoinGecko.
        Use this whenever you are asked to provide a price for a coin.
    Args:
        coin (str): The full, non-truncated currency name to get the price of (e.g. "bitcoin", "ethereum", "solana", "aleph", etc.).
    Returns:
        dict: The price of the coin of the form {"coin": {"usd": price}} if the coin exists, None otherwise.
    """

    # TODO: check that the ticker is valid from coingecko or a hardcoded list -- log a warning if not
    # TODO: raise a proper error to make it easier to catch mistakes downstream
    url = f"{COINGECKO_API_URL}/simple/price?ids={coin}&vs_currencies=usd"
    response = requests.get(url)
    if response.status_code == 200:
        output = response.json()
        # CoinGecko returns an empty dictionary if the coin doesn't exist -- fun :upside_down_face:
        if output == {}:
            raise ValueError(f"CoinGecko does not recognize the coin {coin}.")
        return output
    else:
        raise ValueError(f"CoinGecko returned an error code: {response.status_code}.")