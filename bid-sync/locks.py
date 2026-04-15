import asyncio

process_lock = asyncio.Lock()
extract_lock = asyncio.Lock()
matching_lock = asyncio.Lock()
