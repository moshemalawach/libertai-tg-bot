from .arithmetic import add, sub, mul, div
from .coingecko import coin_price_usd
from .wikipedia import search, summary

# Note: register functions you want to be callable by the bot here
functions = {
    "coingecko.coin_price_usd": coin_price_usd,
    "wikipedia.search": search,
    "wikipedia.summary": summary,
    "arithmetic.add": add,
    "arithmetic.sub": sub,
    "arithmetic.mul": mul,
    "arithmetic.div": div
}