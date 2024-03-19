import re
import ast
import requests
import yfinance as yf
import concurrent.futures

from typing import List
from bs4 import BeautifulSoup
from langchain.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool


# TODO: Investigate logging
@tool
def google_search_and_scrape(query: str) -> dict:
    """
    Performs a Google search for the given query, retrieves the top search result URLs,
    and scrapes the text content and table data from those pages in parallel.

    Args:
        query (str): The search query.
    Returns:
        list: A list of dictionaries containing the URL, text content, and table data for each scraped page.
    """
    num_results = 2
    url = "https://www.google.com/search"
    params = {"q": query, "num": num_results}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.3"
    }

    # inference_logger.info(f"Performing google search with query: {query}\nplease wait...")
    response = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    urls = [
        result.find("a")["href"] for result in soup.find_all("div", class_="tF2Cxc")
    ]

    # inference_logger.info(f"Scraping text from urls, please wait...")
    # [inference_logger.info(url) for url in urls]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                lambda url: (
                    url,
                    requests.get(url, headers=headers).text
                    if isinstance(url, str)
                    else None,
                ),
                url,
            )
            for url in urls[:num_results]
            if isinstance(url, str)
        ]
        results = []
        for future in concurrent.futures.as_completed(futures):
            url, html = future.result()
            soup = BeautifulSoup(html, "html.parser")
            paragraphs = [p.text.strip() for p in soup.find_all("p") if p.text.strip()]
            text_content = " ".join(paragraphs)
            text_content = re.sub(r"\s+", " ", text_content)
            table_data = [
                [cell.get_text(strip=True) for cell in row.find_all("td")]
                for table in soup.find_all("table")
                for row in table.find_all("tr")
            ]
            if text_content or table_data:
                results.append(
                    {"url": url, "content": text_content, "tables": table_data}
                )
    return results


@tool
def get_current_stock_price(symbol: str) -> float | None:
    """
    Get the current stock price for a given symbol.

    Args:
      symbol (str): The stock symbol.

    Returns:
      float: The current stock price, or None if an error occurs.
    """
    try:
        stock = yf.Ticker(symbol)
        # Use "regularMarketPrice" for regular market hours, or "currentPrice" for pre/post market
        current_price = stock.info.get(
            "regularMarketPrice", stock.info.get("currentPrice")
        )
        return current_price if current_price else None
    except Exception as e:
        print(f"Error fetching current price for {symbol}: {e}")
        return None


@tool
def get_current_cryptocurrency_price_usd(symbol: str) -> dict | None:
    """
    Get current price of a cryptocurrency in USD.

    Args:
        symbol (str): The non-truncated cryptocurrency name to get the price of in USD (e.g. "bitcoin", "ethereum", "solana", "aleph", etc.).

    Returns:
        dict: The price of the cryptocurrency in the form {"coin": {"usd": <price>}}, or None if an error occurs.
    """

    url = (
        f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
    )
    response = requests.get(url)
    if response.status_code == 200:
        output = response.json()
        # CoinGecko returns an empty dictionary if the coin doesn't exist -- fun :upside_down_face:
        if output == {}:
            return None
        return output
    else:
        return None


def get_tools() -> List[dict]:
    """
    Get our available tools as OpenAPI-compatible tools
    """

    # Register Functions Here
    functions = [
        google_search_and_scrape,
        get_current_stock_price,
        get_current_cryptocurrency_price_usd,
    ]

    tools = [convert_to_openai_tool(f) for f in functions]
    return tools
