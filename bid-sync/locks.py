import asyncio

process_lock = asyncio.Lock()
extract_lock = asyncio.Lock()
matching_lock = asyncio.Lock()

pre_spec_process_lock = asyncio.Lock()
pre_spec_extract_lock = asyncio.Lock()
pre_spec_matching_lock = asyncio.Lock()


class PerKeyLock:
    """키(company_id 등)별 독립 asyncio.Lock"""

    def __init__(self):
        self._locks: dict = {}

    def get(self, key) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def locked(self, key) -> bool:
        return self._locks[key].locked() if key in self._locks else False


company_matching_lock = PerKeyLock()
company_pre_spec_matching_lock = PerKeyLock()
company_reason_lock = PerKeyLock()
company_pre_spec_reason_lock = PerKeyLock()
