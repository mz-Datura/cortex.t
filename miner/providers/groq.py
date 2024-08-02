import bittensor as bt
from groq import AsyncGroq
from starlette.types import Send

from miner.providers.base import Provider
from miner.config import config
from cortext.protocol import StreamPrompting


class Groq(Provider):
    def __init__(self):
        super().__init__()
        self.groq_client = AsyncGroq(timeout=config.ASYNC_TIME_OUT, api_key=config.GROQ_API_KEY)

    async def _prompt(self, synapse: StreamPrompting, send: Send):
        stream_kwargs = {
            "messages": synapse.messages,
            "model": synapse.model,
            "temperature": synapse.temperature,
            "max_tokens": synapse.max_tokens,
            "top_p": synapse.top_p,
            "seed": synapse.seed,
            "stream": True,
        }

        stream = await self.groq_client.chat.completions.create(**stream_kwargs)
        buffer = []
        n = 1
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            buffer.append(token)
            if len(buffer) == n:
                joined_buffer = "".join(buffer)
                await send(
                    {
                        "type": "http.response.body",
                        "body": joined_buffer.encode("utf-8"),
                        "more_body": True,
                    }
                )
                bt.logging.info(f"Streamed tokens: {joined_buffer}")
                buffer = []

    def image_service(self):
        pass

    def embeddings_service(self):
        pass
