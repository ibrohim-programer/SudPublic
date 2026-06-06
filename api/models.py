# api/models.py — Dataclass modellari
# SudParser v3.0 | publication.sud.uz REST API

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileData:
    """PDF fayl ma'lumotlari"""
    id: int
    name: str
    size: int
    isActive: bool
    isDeleted: bool


@dataclass
class Attachment:
    """Hujjatga biriktirilgan fayl"""
    id: int
    fileData: FileData
    language: str
    external: Optional[str] = None


@dataclass
class PublicationType:
    """Hujjat turi (Qaror, Ajrim, ...)"""
    id: int
    name: str
    nameRu: str = ""


@dataclass
class Publication:
    """Saytdagi bitta sud hujjati"""
    id: int
    publicationType: PublicationType
    claimId: int
    attachmentsList: list[Attachment] = field(default_factory=list)
    dbl: Optional[str] = None

    @property
    def primary_file(self) -> Optional[FileData]:
        """Asosiy (o'chirilmagan) PDF faylni qaytaradi"""
        for att in self.attachmentsList:
            if att.fileData and not att.fileData.isDeleted and att.fileData.isActive:
                return att.fileData
        # Agar hamma o'chirilgan bo'lsa ham birinchisini beradi
        if self.attachmentsList and self.attachmentsList[0].fileData:
            return self.attachmentsList[0].fileData
        return None

    @property
    def download_url(self) -> Optional[str]:
        """Yuklab olish URL si"""
        f = self.primary_file
        if f:
            return f"https://publication.sud.uz/file/{f.id}"
        return None

    @property
    def filename(self) -> str:
        """Lokal fayl nomi: {pub_id}_{original_name}"""
        f = self.primary_file
        if f:
            return f"{self.id}_{f.name}"
        return f"{self.id}.pdf"

    @property
    def size_kb(self) -> float:
        """Fayl hajmi KB da"""
        f = self.primary_file
        if f:
            return round(f.size / 1024, 1)
        return 0.0


@dataclass
class PublicationsResponse:
    """API publications endpoint javobi"""
    content: list[Publication]
    totalPages: int
    totalElements: int
    last: bool
    first: bool
    size: int
    number: int
    numberOfElements: int