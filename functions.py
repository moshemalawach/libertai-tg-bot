import requests
import wikipedia

def add(x: int, y: int) -> int:
    """Add two numbers.
    Args:
        x (int): The first number.
        y (int): The second number.
    Returns:
        int: The sum of the two numbers.
    """
    return x + y

def coingecko_get_price_usd(coin: str) -> dict:
    """Get the up to date USD price of a cryptocurrency from CoinGecko.
        Use this whenever you are asked to provide a price for a coin.
    Args:
        coin (str): The coin symbol to get the price of (e.g. "btc", "eth", "doge", "aleph", etc.).
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

def wikipedia_search(query: str) -> dict:
    """Search Wikipedia for a query. Use this when you are unsure of the exact topic to search for.
    Args:
        query (str): The query to search for.
    Returns:
        list: A list of the top 10 results from Wikipedia.
    """
    return wikipedia.search(query)

def wikipedia_summary(query: str) -> str:
    """Get the summary of a Wikipedia article. Use this whenever you are asked to provide a summary for a topic.
    Args:
        query (str): The query to search for.
    Returns:
        str: The summary of the Wikipedia article.
    """
    return wikipedia.summary(query)