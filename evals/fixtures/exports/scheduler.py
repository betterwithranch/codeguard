class ExportJob:
    def __init__(self, region: str, file_format: str = "csv"):
        self.region = region
        self.file_format = file_format


def export_name(prefix: str, number: int) -> str:
    return f"{prefix}-{number:05d}"


def batch_size(rows: int) -> int:
    if rows < 1_000:
        return rows
    return 1_000


def describe(region: str, count: int) -> str:
    return f"{count} exports for {region}"


def regions(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


class ExportScheduler:
    def __init__(self, queue):
        self.queue = queue

    def schedule(self, region: str) -> None:
        job = ExportJob(region=region, file_format="csv")
        self.queue.put(job)
