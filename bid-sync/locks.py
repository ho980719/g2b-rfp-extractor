import asyncio

process_lock = asyncio.Lock()
extract_lock = asyncio.Lock()
matching_lock = asyncio.Lock()

pre_spec_process_lock = asyncio.Lock()
pre_spec_extract_lock = asyncio.Lock()
pre_spec_matching_lock = asyncio.Lock()
