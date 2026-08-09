"""
Base interface for fetching a retailer's current weekly flyer PDF into
downloads/. Two implementations, chosen per retailer in config.py:

- StaticUrlDownloader: the retailer publishes its current flyer at a
  predictable URL (confirmed by checking their site's network requests --
  see the note in config.py). Fetches it directly via requests.
- ManualDropDownloader: no confirmed auto-fetch method yet. The scheduled
  job logs a reminder instead of failing; someone drops the PDF into
  downloads/ by hand, named per the RETAILER_YYYY-MM-DD_TITLE.pdf convention,
  and the rest of the pipeline picks it up normally on the next run.

Do not guess at a retailer's flyer URL/selector without checking the live
site first -- these pages change layout often and a wrong guess fails
silently (downloads an HTML error page instead of a PDF) rather than loudly.
"""
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import requests

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")


class FlyerDownloader(ABC):
    retailer_code: str

    @abstractmethod
    def fetch(self) -> str | None:
        """Returns the local path of a newly downloaded PDF, or None if nothing new."""
        raise NotImplementedError

    def _dest_path(self, week_end: str | None = None) -> str:
        week_end = week_end or self._default_week_end()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        return os.path.join(DOWNLOAD_DIR, f"{self.retailer_code}_{week_end}_flyer.pdf")

    @staticmethod
    def _default_week_end() -> str:
        # Most AT flyers run Mon-Sun; default to the coming Sunday if not told otherwise.
        today = datetime.now()
        days_ahead = (6 - today.weekday()) % 7
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


class StaticUrlDownloader(FlyerDownloader):
    """For retailers whose current flyer lives at a confirmed, stable URL."""

    def __init__(self, retailer_code: str, url_env_var: str):
        self.retailer_code = retailer_code
        self.url_env_var = url_env_var

    def fetch(self) -> str | None:
        url = os.environ.get(self.url_env_var)
        if not url:
            print(f"[{self.retailer_code}] {self.url_env_var} not set, skipping auto-fetch.")
            return None
        dest = self._dest_path()
        if os.path.exists(dest):
            print(f"[{self.retailer_code}] {dest} already downloaded this week.")
            return dest
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        if resp.headers.get("content-type", "").split(";")[0] != "application/pdf":
            print(f"[{self.retailer_code}] WARNING: response wasn't a PDF (content-type: "
                  f"{resp.headers.get('content-type')}) -- the URL likely needs re-checking against the live site.")
            return None
        with open(dest, "wb") as f:
            f.write(resp.content)
        print(f"[{self.retailer_code}] downloaded flyer to {dest}")
        return dest


class ManualDropDownloader(FlyerDownloader):
    """Placeholder until this retailer's auto-fetch is confirmed and configured."""

    def __init__(self, retailer_code: str):
        self.retailer_code = retailer_code

    def fetch(self) -> str | None:
        print(f"[{self.retailer_code}] no auto-fetch configured yet -- "
              f"drop this week's flyer into {DOWNLOAD_DIR}/ manually "
              f"as '{self.retailer_code}_YYYY-MM-DD_TITLE.pdf'.")
        return None