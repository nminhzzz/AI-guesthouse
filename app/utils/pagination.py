import math


def get_total_pages(total: int, page_size: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def get_offset(page: int, page_size: int) -> int:
    return (page - 1) * page_size
