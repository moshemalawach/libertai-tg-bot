
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