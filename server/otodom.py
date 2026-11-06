"""Strona wyników Otodom w formacie, którego OtodomScraper czyta z `__NEXT_DATA__`."""
import json
import math

from .data import Offer

DEFAULT_LIMIT = 72
ROOMS_ENUM = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR"}
FLOOR_ENUM = {-1: "CELLAR", 0: "GROUND", 1: "FIRST", 2: "SECOND", 3: "THIRD", 4: "FOURTH",
              5: "FIFTH", 6: "SIXTH", 7: "SEVENTH", 8: "EIGHTH", 9: "NINTH", 10: "TENTH"}


def render_results(offers: list[Offer], page: int, limit: int, scenario: str) -> str:
	total_pages = math.ceil(len(offers) / limit)
	# Po ostatniej stronie Otodom ignoruje numer strony i zwraca stronę 1.
	served_page = page if page <= total_pages else 1
	start = (served_page - 1) * limit
	items = offers[start:start + limit]

	search_ads = {
		"pagination": {"currentPage": served_page, "totalPages": total_pages},
		"items": [_item(offer) for offer in items],
	}
	data = {"props": {"pageProps": {"data": {"searchAds": search_ads}}}}
	payload = json.dumps(data, ensure_ascii=False)

	if scenario == "layout_change":
		# Bez __NEXT_DATA__ scraper nie znajdzie searchAds i zwróci pustą stronę.
		return "<!DOCTYPE html><html lang=\"pl\"><head><meta charset=\"utf-8\"></head><body></body></html>"

	return (
		'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">'
		"<title>Sprzedaż mieszkań</title></head><body><div id=\"__next\"></div>"
		f'<script id="__NEXT_DATA__" type="application/json">{payload}</script>'
		"</body></html>"
	)


def parse_limit(raw: str | None) -> int:
	try:
		value = int(raw) if raw else DEFAULT_LIMIT
	except ValueError:
		return DEFAULT_LIMIT
	return max(1, min(value, DEFAULT_LIMIT))


def _item(offer: Offer) -> dict:
	city = {"name": offer.city} if offer.city else None
	locations = [
		{"locationLevel": "voivodeship", "name": offer.region_name},
		{"locationLevel": "city_or_village", "name": offer.city or "Warszawa"},
		{"locationLevel": "district", "name": offer.district},
	]
	return {
		"id": int.from_bytes(offer.code.encode(), "big") % 10**9,
		"slug": offer.otodom_slug,
		"title": offer.title,
		"totalPrice": {"value": offer.price, "currency": "PLN"},
		"pricePerSquareMeter": {"value": offer.price_per_m2, "currency": "PLN"},
		"areaInSquareMeters": offer.area,
		"roomsNumber": ROOMS_ENUM.get(offer.rooms),
		"floorNumber": FLOOR_ENUM.get(offer.floor, "ABOVE_TENTH" if offer.floor > 10 else None),
		"location": {
			"address": {
				"street": {"name": "ul. Przykładowa", "number": "1"} if offer.floor % 2 else None,
				"city": city,
				"province": {"name": offer.region_name},
			},
			"reverseGeocoding": {"locations": locations},
		},
		"images": [{"large": offer.photo}],
		"isPrivateOwner": offer.seller == "private",
		"developmentId": "dev-mock-1" if offer.seller == "developer" else None,
		"agency": {"name": "Biuro Mock"} if offer.seller == "agency" else None,
	}
