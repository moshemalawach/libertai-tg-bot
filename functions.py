import requests

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

# TODO: implement a simple model for this
# TODO: add proper type for ln code -- don't let the AI hallucinate if its generating this  or
#  Provide a safe way to check that the language code is valid
def translate(phrase: str, from_ln: str, to_ln: str) -> str:
    """Translate a phrase from one language to another.
    Args:
        phrase (str): The phrase to translate (text to translate).
        from_ln (str): ISO 639-1 code of the language to translate from.
        to_ln (str): ISO 639-1 code of the language to translate to.
    Returns:
        translation (str): The translated phrase.
    """
    # TODO: Add example of a translation LLM that can be used here
    return "my name jeff"

# TOOD: populate this
class TranslateError(Exception):
    """Base class for exceptions in this module."""
    pass