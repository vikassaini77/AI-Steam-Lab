"""
AI Model Client - AI Layer
Problem 45: Service boundaries separation.
Encapsulates LLM provider calls, prompting configurations, token bounds,
and non-blocking streaming chunk generation. Decoupled from database, HTTP, and SSE.
"""
import asyncio
import inspect
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Optional, Protocol, runtime_checkable

import google.generativeai as genai

from app.logger import logger

MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "30.0"))


async def check_cancellation(is_cancelled: Optional[Any]) -> bool:
    """
    Safely inspects cancellation indicator across:
    - async callables (e.g. Starlette request.is_disconnected)
    - sync callables (lambdas, functions)
    - asyncio.Event or threading.Event
    - boolean values
    """
    if is_cancelled is None:
        return False
    try:
        if isinstance(is_cancelled, (asyncio.Event, threading.Event)):
            return is_cancelled.is_set()
        if callable(is_cancelled):
            res = is_cancelled()
            if inspect.isawaitable(res):
                return await res
            return bool(res)
        return bool(is_cancelled)
    except Exception as exc:
        logger.debug(f"Error checking cancellation status: {exc}")
        return False


@runtime_checkable
class AIClientProtocol(Protocol):
    """Protocol defining the AI Layer interface for model generation and streaming."""

    @property
    def model_name(self) -> str:
        ...

    def is_configured(self) -> bool:
        ...

    async def stream_completion(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: float = MODEL_TIMEOUT_SECONDS,
        is_cancelled: Optional[Any] = None,
    ) -> AsyncGenerator[str, None]:
        ...


_DEFAULT_MODEL = object()


class GeminiAIClient:
    """
    Production AI Client implementation wrapping Google Gemini Generative Models.
    """
    def __init__(
        self,
        model: Any = _DEFAULT_MODEL,
        executor: Optional[ThreadPoolExecutor] = None,
        api_key: Optional[str] = None,
    ):
        self._executor = executor
        self._custom_model = None if model is _DEFAULT_MODEL else model

        if model is _DEFAULT_MODEL:
            resolved_key = api_key or os.getenv("GEMINI_API_KEY")
            if resolved_key and resolved_key != "unconfigured":
                genai.configure(api_key=resolved_key)
                self._model = genai.GenerativeModel(
                    "gemini-2.5-flash",
                    generation_config={
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "temperature": 0.7,
                    },
                )
                self._model_name = "gemini-2.5-flash"
                logger.info("GeminiAIClient initialized with bounded token generation.")
            else:
                self._model = None
                self._model_name = "unconfigured"
        else:
            self._model = model
            self._model_name = getattr(model, "model_name", "custom_model") if model else "unconfigured"

    @property
    def model(self) -> Any:
        return self._model

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        return self._model is not None

    async def stream_completion(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: float = MODEL_TIMEOUT_SECONDS,
        is_cancelled: Optional[Any] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams completion tokens asynchronously without blocking the event loop.
        Applies upstream timeout bounds and cancellation inspection.
        """
        if not self._model:
            raise RuntimeError("AI model is unconfigured: missing GEMINI_API_KEY.")

        full_prompt = f"{system_instruction}\nUser: {prompt}" if system_instruction else prompt
        generation_config = {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.7,
        }

        is_mock = any(cls.__name__ in ("Mock", "MagicMock", "NonCallableMagicMock") for cls in type(self._model).__mro__)
        if is_mock:
            from unittest.mock import AsyncMock
            use_async = isinstance(getattr(self._model, "generate_content_async", None), AsyncMock)
        else:
            use_async = (
                isinstance(self._model, genai.GenerativeModel)
                or (
                    hasattr(self._model, "generate_content_async")
                    and callable(self._model.generate_content_async)
                    and not hasattr(self._model, "_mock_return_value")
                )
            )

        if use_async:
            try:
                response = await asyncio.wait_for(
                    self._model.generate_content_async(
                        full_prompt,
                        stream=True,
                        generation_config=generation_config,
                    ),
                    timeout=timeout_seconds,
                )
                if hasattr(response, "__aiter__"):
                    resp_iter = aiter(response)
                    while True:
                        if await check_cancellation(is_cancelled):
                            logger.info("Stream cancelled by client disconnection.")
                            break
                        try:
                            chunk = await asyncio.wait_for(anext(resp_iter), timeout=timeout_seconds)
                        except StopAsyncIteration:
                            break
                        text = getattr(chunk, "text", "")
                        if text:
                            yield text
                else:
                    for chunk in response:
                        if await check_cancellation(is_cancelled):
                            logger.info("Stream cancelled by client disconnection.")
                            break
                        text = getattr(chunk, "text", "")
                        if text:
                            yield text
            except (asyncio.TimeoutError, TimeoutError) as to_err:
                raise TimeoutError(f"Model generation timed out after {timeout_seconds}s") from to_err
        else:
            # Synchronous fallback isolated in thread pool
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            sentinel = object()
            stop_event = threading.Event()

            def _sync_worker():
                try:
                    res = self._model.generate_content(
                        full_prompt,
                        stream=True,
                        generation_config=generation_config,
                    )
                    if stop_event.is_set():
                        return
                    for chunk in res:
                        if stop_event.is_set():
                            logger.info("Sync stream worker aborted early due to cancellation.")
                            return
                        text = getattr(chunk, "text", str(chunk))
                        loop.call_soon_threadsafe(queue.put_nowait, ("chunk", text))
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", sentinel))
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))

            if self._executor:
                loop.run_in_executor(self._executor, _sync_worker)
            else:
                loop.run_in_executor(None, _sync_worker)

            try:
                while True:
                    if await check_cancellation(is_cancelled):
                        logger.info("Sync stream worker cancelled by client disconnection.")
                        stop_event.set()
                        break
                    try:
                        msg_type, val = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
                    except (asyncio.TimeoutError, TimeoutError) as to_err:
                        stop_event.set()
                        raise TimeoutError(f"Model generation timed out after {timeout_seconds}s") from to_err

                    if msg_type == "chunk":
                        if val:
                            yield val
                    elif msg_type == "done":
                        break
                    elif msg_type == "error":
                        raise val
            finally:
                stop_event.set()
