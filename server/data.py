"""Syntetyczne ogłoszenia dla symulowanych portali.

Dane są losowe, ale powtarzalne (stałe ziarno), więc każdy uruchomiony mock
zwraca dokładnie te same oferty. Nie zawierają prawdziwych ogłoszeń ani
danych osobowych sprzedających.
"""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

SEED = 2026
ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

PROVINCES = (
	"slaskie", "mazowieckie", "dolnoslaskie", "wielkopolskie", "pomorskie", "zachodniopomorskie",
	"malopolskie", "lodzkie", "kujawsko-pomorskie", "lubelskie", "warminsko-mazurskie",
	"podkarpackie", "lubuskie", "swietokrzyskie", "podlaskie", "opolskie")

# slug województwa -> (nazwa, {miasto: [dzielnice]}, liczba ogłoszeń)
# Województwa bez wpisu nie mają ofert, tak jak rzadko używany region w prawdziwym portalu.
REGIONS = {
	"mazowieckie": ("Mazowieckie", {"Warszawa": ["Mokotów", "Wola", "Ursynów", "Praga-Północ"],
	                                "Radom": ["Śródmieście"]}, 1400),
	"malopolskie": ("Małopolskie", {"Kraków": ["Krowodrza", "Podgórze", "Nowa Huta"]}, 350),
	"dolnoslaskie": ("Dolnośląskie", {"Wrocław": ["Fabryczna", "Krzyki", "Śródmieście"]}, 260),
	"slaskie": ("Śląskie", {"Katowice": ["Śródmieście", "Ligota"]}, 220),
	"pomorskie": ("Pomorskie", {"Gdańsk": ["Wrzeszcz", "Oliwa"]}, 180),
	"wielkopolskie": ("Wielkopolskie", {"Poznań": ["Jeżyce", "Grunwald"]}, 160),
}

PHOTO_HOST = "https://img.portal-mock.test"


@dataclass
class Offer:
	code: str
	title: str
	rooms: int
	area: float
	price: int
	price_per_m2: int
	floor: int
	floor_in_title: bool
	city: Optional[str]
	district: str
	region_slug: str
	region_name: str
	seller: str  # "private", "agency" albo "developer"
	olx_external: bool  # True = ogłoszenie na OLX linkuje do Otodomu (scraper je pomija)
	photo: str
	created_at: datetime

	@property
	def olx_href(self) -> str:
		if self.olx_external:
			return f"https://www.otodom.pl/pl/oferta/mieszkanie-{self.code}"
		return f"/d/oferta/mieszkanie-{self.rooms}-pokoje-ID{self.code}.html"

	@property
	def otodom_slug(self) -> str:
		return f"mieszkanie-{self.rooms}-pokoje-ID{self.code}"


def build_offers(seed: int = SEED) -> list[Offer]:
	rng = random.Random(seed)
	used_codes: set[str] = set()
	start = datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)
	offers: list[Offer] = []

	for region_slug, (region_name, cities, count) in REGIONS.items():
		for index in range(count):
			code = _unique_code(rng, used_codes)
			city_name = rng.choice(list(cities))
			district = rng.choice(cities[city_name])
			rooms = rng.choice([1, 2, 2, 3, 3, 3, 4])
			area = round(rooms * 18 + rng.uniform(-6, 14), 1)
			price_per_m2 = rng.randint(750, 1650) * 10
			price = round(area * price_per_m2 / 1000) * 1000
			floor = rng.choice([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
			floor_in_title = floor > 0 and rng.random() < 0.6
			rooms_word = "pokój" if rooms == 1 else "pokoje"
			title = f"Mieszkanie {rooms} {rooms_word}"
			if floor_in_title:
				title += f", {floor} piętro"
			seller = rng.choices(["private", "agency", "developer"], weights=[5, 3, 2])[0]
			offers.append(Offer(
				code=code,
				title=title,
				rooms=rooms,
				area=area,
				price=price,
				price_per_m2=round(price / area),
				floor=floor,
				floor_in_title=floor_in_title,
				# ok. 10% ogłoszeń nie ma miasta w adresie (portal dopełnia je z geokodowania)
				city=city_name if rng.random() > 0.1 else None,
				district=district,
				region_slug=region_slug,
				region_name=region_name,
				seller=seller,
				olx_external=rng.random() < 0.08,
				photo=f"{PHOTO_HOST}/{code}.jpg",
				created_at=start - timedelta(minutes=index * 7 + len(offers)),
			))
	return offers


def _unique_code(rng: random.Random, used: set[str]) -> str:
	while True:
		code = "".join(rng.choice(ALPHABET) for _ in range(6))
		if code not in used:
			used.add(code)
			return code
