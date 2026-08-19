import logging
from typing import Type, TypeVar, Any
from openai import AsyncOpenAI
from pydantic import BaseModel
from .config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

T = TypeVar("T", bound=BaseModel)

async def reason(system_prompt: str, user_content: str, model: str) -> str:
    """Send a chat completion and get a string response."""
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content

async def reason_structured(
    system_prompt: str, 
    user_content: str, 
    model: str, 
    response_format: Type[T]
) -> T:
    """Use OpenAI's structured output (JSON mode) to get a guaranteed-parseable object."""
    response = await client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format=response_format,
        temperature=0.2,
    )
    return response.choices[0].message.parsed
