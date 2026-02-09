import asyncio


def run_async(coro):
    """Helper untuk menjalankan coroutine dengan handling loop per-thread."""
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        # Fallback if we are already in a loop (unlikely with this thread model)
        if "loops" in str(e):
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)
             return loop.run_until_complete(coro)
        raise e