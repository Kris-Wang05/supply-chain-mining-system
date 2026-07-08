from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass, field

# SEC 要求：自定义 User-Agent（含联系方式），请求频率 <= 10 req/s。
# 联系邮箱从环境或配置注入；默认值必须在部署时替换。
SEC_USER_AGENT = "discovery-engine research (contact: boc25327@gmail.com)"
MIN_REQUEST_INTERVAL_SECONDS = 0.15  # ~6.7 req/s，留安全余量


@dataclass
class RateLimitedFetcher:
    """带最小间隔的 HTTP GET。所有采集器共用，禁止绕过它直接发请求。"""

    user_agent: str = SEC_USER_AGENT
    min_interval: float = MIN_REQUEST_INTERVAL_SECONDS
    timeout: float = 30.0
    _last_request_at: float = field(default=0.0, repr=False)

    def get(self, url: str) -> bytes:
        wait = self.min_interval - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read()
        self._last_request_at = time.monotonic()
        return body

    def get_text(self, url: str) -> str:
        return self.get(url).decode("utf-8", errors="replace")


@dataclass(frozen=True)
class RawFiling:
    """采集器输出的最小单元。只存事实，不做任何评分或判断。

    accession 是 EDGAR 全局唯一编号，作为 raw 层去重键。
    """

    accession: str
    form_type: str
    cik: str
    company: str
    filed_date: str
    source_url: str
    captured_at: str
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "accession": self.accession,
            "form_type": self.form_type,
            "cik": self.cik,
            "company": self.company,
            "filed_date": self.filed_date,
            "source_url": self.source_url,
            "captured_at": self.captured_at,
            "extra": dict(self.extra),
        }
