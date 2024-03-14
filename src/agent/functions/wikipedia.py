import wikipedia

def search(query: str) -> dict:
    """Search Wikipedia for a query. Use this when you are unsure of the exact topic to search for.
    Combine this with summary to find the exact article to summarize after you have found the correct topic.
    Args:
        query (str): The query to search for.
    Returns:
        list: A list of the top 10 RELATED TOPICS or SUBJECTS from Wikipedia.
    """
    return wikipedia.search(query)


def summary(query: str) -> str:
    """Get the summary of a Wikipedia article. Use this whenever you are asked to provide a SUMMARY of a SUBJECT or TOPIC.
    Combine this with search to find which article to summarize if you are unsure of the exact topic to search for.
    Args:
        query (str): The query to search for.
    Returns:
        str: The summary of the Wikipedia article.
    """
    return wikipedia.summary(query)