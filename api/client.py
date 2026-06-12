# api/client.py — publication.sud.uz REST API bilan ishlash
# SudParser v3.0 | Selenium kerak emas — to'liq JSON API

import requests
import time
import json
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
        return self._unwrap(r.json())

    def get_categories(self) -> list[dict]:
        """Kategoriyalarni olish (/category)"""
        r = self._get(CATEGORY_URL)
        return self._unwrap(r.json())

    def get_courts(self, court_level: int) -> list[dict]:
        """
        Berilgan sud darajasi (courtType: 1=Oliy, 2=Viloyat, 3=Tuman) bo'yicha
        sudlar ro'yxati. [{"id":..,"name":..}, ...]
        """
        try:
            r = self._get(f"{BASE_URL}/unauthorized/courts", params={"courtType": court_level})
            d = self._unwrap(r.json())
            return d if isinstance(d, list) else []
        except Exception:
            return []

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
        return self._parse_response(self._unwrap(r.json()))

    def fetch_raw_page(
        self,
        court_type: str,
        page: int = 0,
        size: int = 50,
        start_date_ms: Optional[int] = None,
        end_date_ms: Optional[int] = None,
        type_id: Optional[int] = None,
        case_number: Optional[str] = None,
        instance_type: Optional[str] = None,
        category: Optional[int] = None,
        judge: Optional[str] = None,
        court_level: Optional[int] = None,
        court_name: Optional[str] = None,
    ) -> dict:
        """
        Sahifani XOM (raw) holda olish — barcha maydonlar bilan
        (judge, caseNumber, instance, hearingDate, result, sud nomi...).
        Qaytaradi: {"content": [dict...], "totalElements": n, "totalPages": n, "last": bool}
        """
        params: dict = {"size": size, "page": page, "court_type": court_type}
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
        if category:
            params["category"] = category
        if judge and judge.strip():
            params["judge"] = judge.strip()
        if court_level:
            params["courtType"] = court_level
        if court_name and court_name.strip():
            # Sud bo'yicha filtr — sud NOMI orqali (dbName param ishlaydi)
            params["dbName"] = court_name.strip()

        r = self._get(PUBLICATIONS_URL, params=params)
        d = self._unwrap(r.json())
        if not isinstance(d, dict):
            d = {}
        return d

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
        """PDF faylni bytes sifatida yuklab olish (kam retry — uzoq osilmasin)"""
        r = self._get(
            f"{BASE_URL}/api/file/download/{file_id}",
            stream=True, timeout=45, max_retries=3,
        )
        return r.content

    def report_counts(self) -> Optional[dict]:
        """
        Iqtisodiy sudlar bo'yicha umumiy sonlar (publication.sud.uz/report/counts).
        Qaytaradi: {"total":n, "first":n, "appeal":n, "cassation":n, "control":n}
        yoki None (xatoda).
        Maydonlar: first=Биринчи, appeal=Апелляция, cassation=Кассация,
                   control=Тафтиш, allI=umumiy.
        """
        try:
            r = self._get(f"{BASE_URL}/report/counts", max_retries=2)
            d = self._unwrap(r.json())
            if isinstance(d, str):
                d = json.loads(d)
            return {
                "total":     d.get("allI"),
                "first":     d.get("first"),
                "appeal":    d.get("appeal"),
                "cassation": d.get("cassation"),
                "control":   d.get("control"),
            }
        except Exception:
            return None

    # ─── Ichki yordamchi metodlar ────────────────────────────────────────────

    @staticmethod
    def _unwrap(payload):
        """
        API javobini "data" o'ramidan ochadi.
        Yangi API barcha javobni {"data": "<JSON satr>"} ko'rinishida qaytaradi.
        Eski format (to'g'ridan-to'g'ri dict/list) ham qo'llab-quvvatlanadi.
        """
        if isinstance(payload, dict) and "data" in payload and len(payload) == 1:
            inner = payload["data"]
            if isinstance(inner, str):
                try:
                    return json.loads(inner)
                except (ValueError, TypeError):
                    return inner
            return inner
        return payload

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
        # Connect (ulanish) bosqichini 10s bilan cheklaymiz — sayt bloklasa
        # dastur 60s osilib qolmasin. (connect, read) ko'rinishida.
        _connect_to = min(10, _timeout)
        _eff_timeout = (_connect_to, _timeout)

        for attempt in range(_retries):
            try:
                r = self.session.get(url, params=params, timeout=_eff_timeout, stream=stream)

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

            except requests.ConnectionError:
                # Ulanish rad etildi / vaqtincha uzildi — kutib qayta urinamiz
                if attempt == _retries - 1:
                    raise
                time.sleep(3 * (attempt + 1))

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