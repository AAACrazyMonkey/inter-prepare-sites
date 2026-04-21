"""LLM client wrapper. Uses OpenAI-compatible API (works with DeepSeek, OpenAI, etc.)."""

import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


def get_llm_client() -> AsyncOpenAI:
    """Create an async LLM client using DeepSeek or any OpenAI-compatible API."""
    return AsyncOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


# Default model - change this if using a different DeepSeek model
DEFAULT_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


async def chat_completion(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Send a chat completion request and return the response text."""
    client = get_llm_client()
    model = model or DEFAULT_MODEL

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content

async def chat_completion_stream(
    messages: list[dict],
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Stream chat completion, yields text chunks."""
    client = get_llm_client()
    model = model or DEFAULT_MODEL

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content