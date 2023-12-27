import requests

def coingecko_get_price(coin: str) -> dict:
    """Get the USD price of a coin from coingecko.
    Args:
        coin (str): The coin ticker.
    Returns:
        dict: The price of the coin of the form {"coin": {"usd": price}} if the coin exists, None otherwise.
    """

    # TODO: check that the ticker is valid from coingecko or a hardcoded list -- log a warning if not
    # TODO: raise a proper error to make it easier to catch mistakes downstream
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd"
    response = requests.get(url)
    if response.status_code == 200:
        output = response.json()
        # CoinGecko returns an empty dictionary if the coin doesn't exist -- fun :upside_down_face:
        if output == {}:
            return None
        return output
    else:
        return None