# api/client.py — publication.sud.uz REST API bilan ishlash
# SudParser v3.0 | Selenium kerak emas — to'liq JSON API

import requests
import time
from typing import Iterator, Optional
from .models import Publication, PublicationsResponse, PublicationType, Attachment, FileData
from .endpoints import BASE_URL, PUBLICATIONS_URL, TYPES_URL, CATEGORY_URL


class SudApiClient:
    """
    publication.sud.uz REST API bilan ishlash.
    Selenium kerak emas — API to'liq JSON qaytaradi.
    requests.Session() ishlatiladi — har safar yangi connection ochilmaydi.
    """

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8",
            "Origin": "https://public.sud.uz",
            "Referer": "https://public.sud.uz/",
        })

    # ─── Ommaviy metodlar ────────────────────────────────────────────────────

    def get_types(self) -> list[dict]:
        """Hujjat turlarini olish (/types)"""
        r = self._get(TYPES_URL)
        return r.json()

    def get_categories(self) -> list[dict]:
        """Kategoriyalarni olish (/category)"""
        r = self._get(f"{BASE_URL}/category")
        return r.json()

    def fetch_page(
        self,
        court_type: str,
        page: int = 0,
        size: int = 30,
        start_date_ms: Optional[int] = None,
        end_date_ms: Optional[int] = None,
        type_id: Optional[int] = None,
        case_number: Optional[str] = None,
        instance_type: Optional[str] = None,
    ) -> PublicationsResponse:
        """
        Bitta sahifani olish.
        MUHIM: startDate ni hech qachon null yuborma — 400 xato beradi!
        Shuning uchun faqat berilganda parametrga qo'shiladi.
        """
        params: dict = {
            "size": size,
            "page": page,
            "court_type": court_type,
        }
        # Null yuborilmasligi uchun faqat mavjud qiymatlar qo'shiladi
        if start_date_ms is not None:
            params["startDate"] = start_date_ms
        if end_date_ms is not None:
            params["endDate"] = end_date_ms
        if type_id:
            params["typeId"] = type_id
        if case_number and case_number.strip():
            params["caseNumber"] = case_number.strip()
        if instance_type and instance_type.strip():
            params["instanceType"] = instance_type.strip()

        r = self._get(PUBLICATIONS_URL, params=params)
        return self._parse_response(r.json())

    def iter_all_pages(
        self,
        court_type: str,
        stop_event=None,
        **kwargs,
    ) -> Iterator[Publication]:
        """
        Barcha sahifalarni ketma-ket o'tib, hujjatlar generatori.
        stop_event berilsa — to'xtatish signali kuzatiladi.
        """
        page = 0
        while True:
            if stop_event and stop_event.is_set():
                break
            resp = self.fetch_page(court_type, page=page, **kwargs)
            yield from resp.content
            if resp.last or page >= resp.totalPages - 1:
                break
            page += 1
            time.sleep(self.config.request_delay)

    def get_latest(self, court_type: str, size: int = 50) -> list[Publication]:
        """
        Monitoring uchun: faqat 1-sahifani olib, eng yangi hujjatlarni qaytaradi.
        Sayt hujjatlarni ID bo'yicha tartiblaydi (katta ID = yangi).
        """
        resp = self.fetch_page(court_type, page=0, size=size)
        return resp.content

    def download_file_bytes(self, file_id: int) -> bytes:
        """PDF faylni bytes sifatida yuklab olish"""
        r = self._get(f"{BASE_URL}/file/{file_id}", stream=True, timeout=60)
        return r.content

    # ─── Ichki yordamchi metodlar ────────────────────────────────────────────

    def _get(
        self,
        url: str,
        params: Optional[dict] = None,
        stream: bool = False,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> requests.Response:
        """
        Exponential backoff bilan GET so'rov.
        HTTP 429 → 30s kutish
        HTTP 5xx / Timeout → 3 marta retry
        HTTP 400 / 404 → darhol exception
        """
        _timeout = timeout or self.config.timeout
        _retries = max_retries or self.config.retry_count

        for attempt in range(_retries):
            try:
                r = self.session.get(url, params=params, timeout=_timeout, stream=stream)

                # Rate limit — kuting
                if r.status_code == 429:
                    wait_s = 30 * (attempt + 1)
                    time.sleep(wait_s)
                    continue

                # Darhol to'xtatilsin
                if r.status_code in (400, 404):
                    r.raise_for_status()

                r.raise_for_status()
                return r

            except requests.Timeout:
                if attempt == _retries - 1:
                    raise
                time.sleep(2 ** attempt)

            except requests.HTTPError:
                if r.status_code in (400, 404):
                    raise
                if attempt == _retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Max retries ({_retries}) oshdi: {url}")

    @staticmethod
    def _parse_response(data: dict) -> PublicationsResponse:
        """JSON dict → PublicationsResponse dataclass"""
        content: list[Publication] = []
        for item in data.get("content", []):
            # PublicationType
            pt_raw = item.get("publicationType") or {}
            pub_type = PublicationType(
                id=pt_raw.get("id", 0),
                name=pt_raw.get("name", ""),
                nameRu=pt_raw.get("nameRu", ""),
            )
            # Attachments
            attachments: list[Attachment] = []
            for att in item.get("attachmentsList", []):
                fd_raw = att.get("fileData") or {}
                if fd_raw:
                    attachments.append(Attachment(
                        id=att.get("id", 0),
                        fileData=FileData(
                            id=fd_raw.get("id", 0),
                            name=fd_raw.get("name", ""),
                            size=fd_raw.get("size", 0),
                            isActive=fd_raw.get("isActive", True),
                            isDeleted=fd_raw.get("isDeleted", False),
                        ),
                        language=att.get("language", "uz"),
                        external=att.get("external"),
                    ))
            content.append(Publication(
                id=item["id"],
                publicationType=pub_type,
                claimId=item.get("claimId", 0),
                attachmentsList=attachments,
                dbl=item.get("dbl"),
            ))

        return PublicationsResponse(
            content=content,
            totalPages=data.get("totalPages", 0),
            totalElements=data.get("totalElements", 0),
            last=data.get("last", True),
            first=data.get("first", True),
            size=data.get("size", 30),
            number=data.get("number", 0),
            numberOfElements=data.get("numberOfElements", 0),
        )