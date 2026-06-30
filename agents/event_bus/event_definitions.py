"""
AGU Formula Student FCEV — Olay Tanımları (Event Definitions)
=============================================================
Bu modül, çok-etmen sistemin olay yolunun (event bus) temelini oluşturur.
Tüm etmenler arasındaki iletişim bu dosyada tanımlanan olay türleriyle yönetilir.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# FCEV Olay Türleri
# ---------------------------------------------------------------------------

class FCEVEvent(Enum):
    """
    AGU Formula Student FCEV sisteminde kullanılan tüm olay türlerini tanımlar.

    Kategoriler:
        - Donanım (Hardware): Araç bileşenlerine ilişkin olaylar
        - Telemetri (Telemetry): Sensör ve anlık veri olayları
        - Dış Kaynak (External): Akademik, kural ve sponsor olayları
        - Kod (Code): Yazılım geliştirme sürecine ait olaylar
    """

    # ------------------------------------------------------------------
    # Donanım Olayları (Hardware Events)
    # ------------------------------------------------------------------

    NEW_COMPONENT_ADDED = "new_component_added"
    """Araç tasarımına yeni bir fiziksel bileşen eklendiğinde tetiklenir."""

    COMPONENT_SPECS_UPDATED = "component_specs_updated"
    """Mevcut bir bileşenin teknik özellikleri güncellendiğinde tetiklenir."""

    MOTOR_FOUND = "motor_found"
    """Elektrik motoru seçimi tamamlandığında tetiklenir."""

    FUEL_CELL_CONFIRMED = "fuel_cell_confirmed"
    """Yakıt hücresi modeli onaylandığında tetiklenir."""

    # ------------------------------------------------------------------
    # Telemetri Olayları (Telemetry Events)
    # ------------------------------------------------------------------

    SENSOR_ANOMALY = "sensor_anomaly"
    """Sensör verilerinde anormallik tespit edildiğinde tetiklenir (uyarı seviyesi)."""

    SENSOR_CRITICAL = "sensor_critical"
    """Sensör verilerinde kritik bir durum oluştuğunda tetiklenir (acil müdahale)."""

    LAP_COMPLETED = "lap_completed"
    """Simülasyonda veya gerçek testte bir tur tamamlandığında tetiklenir."""

    BATTERY_LOW = "battery_low"
    """Batarya şarjı kritik seviyenin altına düştüğünde tetiklenir."""

    FC_THERMAL_WARNING = "fc_thermal_warning"
    """Yakıt hücresi ısısı güvenli eşiği aştığında tetiklenir."""

    # ------------------------------------------------------------------
    # Dış Kaynak Olayları (External Events)
    # ------------------------------------------------------------------

    NEW_ARXIV_PAPER = "new_arxiv_paper"
    """ArXiv üzerinde ilgili yeni bir akademik makale yayımlandığında tetiklenir."""

    FS_RULES_UPDATED = "fs_rules_updated"
    """Formula Student resmi kuralları güncellendiğinde tetiklenir."""

    SPONSOR_RESPONDED = "sponsor_responded"
    """Potansiyel sponsor e-postaya veya teklife yanıt verdiğinde tetiklenir."""

    SPONSOR_AGREED = "sponsor_agreed"
    """Sponsor sponsorluğu resmi olarak kabul ettiğinde tetiklenir."""

    # ------------------------------------------------------------------
    # Kod Olayları (Code Events)
    # ------------------------------------------------------------------

    NEW_COMMIT_MAIN = "new_commit_main"
    """Main dalına yeni bir commit gönderildiğinde tetiklenir."""

    CRITICAL_BUG_FOUND = "critical_bug_found"
    """Kod analizinde kritik bir hata tespit edildiğinde tetiklenir."""


# ---------------------------------------------------------------------------
# Olay Öncelik Haritası
# ---------------------------------------------------------------------------

PRIORITY_MAP: dict[FCEVEvent, int] = {
    # --- Kritik (10) ---
    FCEVEvent.SENSOR_CRITICAL: 10,

    # --- Yüksek (8) ---
    FCEVEvent.MOTOR_FOUND: 8,

    # --- Orta-Yüksek (7) ---
    FCEVEvent.SPONSOR_AGREED: 7,

    # --- Standart (5) ---
    FCEVEvent.NEW_COMPONENT_ADDED: 5,
    FCEVEvent.COMPONENT_SPECS_UPDATED: 5,
    FCEVEvent.FUEL_CELL_CONFIRMED: 5,
    FCEVEvent.SENSOR_ANOMALY: 5,
    FCEVEvent.LAP_COMPLETED: 5,
    FCEVEvent.BATTERY_LOW: 5,
    FCEVEvent.FC_THERMAL_WARNING: 5,
    FCEVEvent.NEW_ARXIV_PAPER: 5,
    FCEVEvent.FS_RULES_UPDATED: 5,
    FCEVEvent.SPONSOR_RESPONDED: 5,
    FCEVEvent.NEW_COMMIT_MAIN: 5,
    FCEVEvent.CRITICAL_BUG_FOUND: 5,
}


# ---------------------------------------------------------------------------
# Olay Yükü Veri Sınıfı (Event Payload Dataclass)
# ---------------------------------------------------------------------------

@dataclass
class EventPayload:
    """
    Olay yolunda (event bus) taşınan mesajın yapısını tanımlar.

    Her olay bu yapı üzerinden iletilir; etmenler bu nesneyi alarak
    olay türünü, zamanını, içeriğini ve önceliğini belirler.

    Attributes:
        event_type (FCEVEvent): Olayın türü.
        timestamp (datetime): Olayın oluşturulduğu zaman damgası.
        data (dict): Olaya özgü serbest biçimli veri alanı.
        source (str): Olayı tetikleyen etmen veya modülün adı.
        priority (int): Olayın önceliği (1=düşük, 10=kritik). Varsayılan: 1.
    """

    event_type: FCEVEvent
    timestamp: datetime
    data: dict = field(default_factory=dict)
    source: str = "unknown"
    priority: int = 1

    def __post_init__(self):
        """
        Başlatma sonrası doğrulama ve otomatik öncelik atama.
        Eğer öncelik varsayılan (1) olarak bırakılmışsa, PRIORITY_MAP'ten alınır.
        """
        if self.priority == 1 and self.event_type in PRIORITY_MAP:
            self.priority = PRIORITY_MAP[self.event_type]

    def to_dict(self) -> dict:
        """
        EventPayload nesnesini JSON serileştirmeye uygun sözlük biçimine dönüştürür.

        Returns:
            dict: Olay yükünün sözlük temsili.
        """
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "EventPayload":
        """
        Sözlük biçiminden EventPayload nesnesi oluşturur (örn. Pub/Sub mesajı).

        Args:
            raw (dict): Ham sözlük verisi.

        Returns:
            EventPayload: Yeniden oluşturulmuş olay yükü nesnesi.
        """
        return cls(
            event_type=FCEVEvent(raw["event_type"]),
            timestamp=datetime.fromisoformat(raw["timestamp"]),
            data=raw.get("data", {}),
            source=raw.get("source", "unknown"),
            priority=raw.get("priority", 1),
        )
