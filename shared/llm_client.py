"""
llm_client.py — Anthropic API wrapper for the PoC Platform.

Provides a thin, reusable client around the Anthropic Python SDK with
consistent error handling and a convenience method for context-grounded
queries.

Usage:
    from shared.llm_client import llm

    answer = llm.query("Summarize this document.", system_message="You are a helpful assistant.")
    answer = llm.query_with_context("What are the payment terms?", context=doc_text)
"""

import anthropic

from shared.config import Config


class LLMClient:
    """
    Wrapper around the Anthropic Messages API.

    Instantiates a single `anthropic.Anthropic` client and exposes two
    query methods that handle common error cases uniformly.
    """

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self) -> None:
        """
        Initialise the Anthropic client.

        Reads the API key from Config.ANTHROPIC_API_KEY. Raises no error
        here — errors surface on the first API call if the key is missing.
        """
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = self.DEFAULT_MODEL

    def query(
        self,
        prompt: str,
        system_message: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send a single-turn prompt to the Anthropic Messages API.

        Args:
            prompt:         The user-facing question or instruction.
            system_message: Optional system prompt that sets model behaviour.
            max_tokens:     Maximum tokens to generate. Defaults to 2000.

        Returns:
            The model's text response as a plain string.

        Raises:
            Returns an error string rather than raising, so callers can
            display the message directly in Streamlit without a try/except.
        """
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_message:
            kwargs["system"] = system_message

        try:
            response = self.client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            return (
                "Rate limit reached. Please wait a moment and try again. "
                "If this persists, check your Anthropic plan usage limits."
            )
        except anthropic.APIConnectionError:
            return (
                "Could not connect to the Anthropic API. "
                "Check your network connection and try again."
            )
        except anthropic.APIError as exc:
            return f"Anthropic API error ({exc.status_code}): {exc.message}"
        except Exception as exc:  # noqa: BLE001
            return f"Unexpected error: {str(exc)}"

    def query_with_context(
        self,
        prompt: str,
        context: str,
        system_message: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send a prompt grounded in a text context block.

        The context is prepended to the user message so the model can
        reference it when answering the question.

        Args:
            prompt:         The user's question about the context.
            context:        The reference text (document, data extract, etc.).
            system_message: Optional system prompt.
            max_tokens:     Maximum tokens to generate. Defaults to 2000.

        Returns:
            The model's text response as a plain string.
        """
        grounded_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
        return self.query(
            prompt=grounded_prompt,
            system_message=system_message,
            max_tokens=max_tokens,
        )

    def query_with_usage(
        self,
        prompt: str,
        system_message: str | None = None,
        max_tokens: int = 2000,
    ) -> tuple[str, int]:
        """
        Like query(), but also returns the total token count for usage tracking.

        Returns
        -------
        tuple[str, int]
            ``(response_text, total_tokens)``.
            ``total_tokens`` is 0 when an API error occurs.
        """
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_message:
            kwargs["system"] = system_message

        try:
            response = self.client.messages.create(**kwargs)
            total_tokens = response.usage.input_tokens + response.usage.output_tokens
            return response.content[0].text, total_tokens

        except anthropic.RateLimitError:
            return (
                "Rate limit reached. Please wait a moment and try again. "
                "If this persists, check your Anthropic plan usage limits.",
                0,
            )
        except anthropic.APIConnectionError:
            return (
                "Could not connect to the Anthropic API. "
                "Check your network connection and try again.",
                0,
            )
        except anthropic.APIError as exc:
            return f"Anthropic API error ({exc.status_code}): {exc.message}", 0
        except Exception as exc:  # noqa: BLE001
            return f"Unexpected error: {str(exc)}", 0

    def query_with_context_with_usage(
        self,
        prompt: str,
        context: str,
        system_message: str | None = None,
        max_tokens: int = 2000,
    ) -> tuple[str, int]:
        """
        Like query_with_context(), but also returns the total token count.

        Returns
        -------
        tuple[str, int]
            ``(response_text, total_tokens)``.
            ``total_tokens`` is 0 when an API error occurs.
        """
        grounded_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
        return self.query_with_usage(
            prompt=grounded_prompt,
            system_message=system_message,
            max_tokens=max_tokens,
        )


# Module-level singleton — lazy init so import doesn't fail when key is absent
try:
    llm = LLMClient()
except Exception:  # noqa: BLE001
    llm = None  # type: ignore[assignment]
