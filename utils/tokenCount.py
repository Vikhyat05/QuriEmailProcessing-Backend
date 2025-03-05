import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Calculates the number of tokens in a given string using OpenAI's tokenizer.

    :param text: The input string to tokenize.
    :param model: The model name (default is "gpt-4o").
                  Other options: "gpt-4", "gpt-3.5-turbo", etc.
    :return: The number of tokens in the input text.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding(
            "cl100k_base"
        )  # Fallback for unsupported models

    token_count = len(encoding.encode(text))
    return token_count
