import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def run_async(coro):
    """Helper untuk menjalankan coroutine dengan handling loop."""
    try:
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        if "loop is closed" in str(e):
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(coro)
        else:
            raise