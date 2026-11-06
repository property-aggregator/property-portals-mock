"""Strona listingu OLX w formacie, którego oczekuje OlxScraper.

Scraper czyta: karty `data-testid="l-card"`, link `/d/oferta/...`, `ad-price`,
`location-date`, `blueprint-card-param-icon`, `pagination-forward` oraz stan
`__PRERENDERED_STATE__=` z `pageNumber`, `totalPages`, `totalElements` i `ads`.
"""
import html
import json
from datetime import timezone

from .data import Offer

PAGE_SIZE = 40
MAX_PAGES = 25  # OLX pokazuje max 25 stron na zapytanie
MAX_ELEMENTS = 1000  # totalElements jest ucinane do 1000
ROOM_PARAM = {1: "one", 2: "two", 3: "three", 4: "four"}
NBSP = "\u00a0"


def render_listing(offers: list[Offer], page: int, total: int, scenario: str) -> str:
	total_pages = min(MAX_PAGES, -(-total // PAGE_SIZE))
	page_offers = offers[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]

	parts = ["<!DOCTYPE html>", '<html lang="pl">', "<head>", '<meta charset="utf-8">',
	         "<title>Mieszkania na sprzedaż</title>", "</head>", "<body>"]

	if scenario != "no_state":
		state = {"listing": {"listing": {
			"pageNumber": page - 1,
			"totalPages": total_pages,
			"totalElements": min(total, MAX_ELEMENTS),
			"ads": [_ad_state(offer) for offer in page_offers if not offer.olx_external],
		}}}
		# Marker musi być dokładnie `__PRERENDERED_STATE__=` (bez spacji przed znakiem równości).
		parts.append(f"<script>window.__PRERENDERED_STATE__={json.dumps(state, ensure_ascii=False)}</script>")

	parts.append('<div class="listing-grid">')
	for offer in page_offers:
		parts.append(_card(offer, scenario))
	parts.append("</div>")

	if page < total_pages:
		parts.append(f'<a data-testid="pagination-forward" href="?page={page + 1}">Dalej</a>')
	parts.append("</body></html>")
	return "\n".join(parts)


def _card(offer: Offer, scenario: str) -> str:
	if scenario == "layout_change":
		# Zmieniony układ: bez atrybutów data-testid, scraper nie znajdzie kart.
		return (f'<article class="card"><a href="{offer.olx_href}">'
		        f'<h4>{html.escape(offer.title)}</h4></a></article>')

	hour, minute = divmod((offer.created_at.hour * 60 + offer.created_at.minute + 37) % 1440, 60)
	price = f"{offer.price:,}".replace(",", NBSP) + f"{NBSP}zł"
	ppm = f"{offer.price_per_m2:,}".replace(",", NBSP)
	area = f"{offer.area:g}"
	city = offer.city or "Warszawa"
	location = f"{city}, {offer.district} - Dzisiaj o {hour:02d}:{minute:02d}"
	params = f"{area}{NBSP}m²{NBSP}{ppm}{NBSP}zł/m²"
	return (
		'<div data-testid="l-card">'
		f'<a href="{offer.olx_href}"><img src="{offer.photo}" alt=""></a>'
		f'<h4 class="title">{html.escape(offer.title)}</h4>'
		f'<p data-testid="ad-price">{price}<span>netto</span></p>'
		f'<p data-testid="location-date">{html.escape(location)}</p>'
		f'<span data-testid="blueprint-card-param-icon"><svg width="12"><path d="M0"></path></svg>'
		f' {params}</span>'
		"</div>"
	)


def _ad_state(offer: Offer) -> dict:
	floor_value = offer.floor
	return {
		"url": f"https://www.olx.pl{offer.olx_href}",
		"params": [
			{"key": "m", "normalizedValue": f"{offer.area:g}"},
			{"key": "price_per_m", "normalizedValue": str(offer.price_per_m2)},
			{"key": "rooms", "normalizedValue": ROOM_PARAM.get(offer.rooms)},
			{"key": "floor_select", "normalizedValue": f"floor_{floor_value}"},
		],
		"location": {
			"cityName": offer.city,
			"districtName": offer.district,
			"regionName": offer.region_name,
		},
		"isBusiness": offer.seller != "private",
		"photos": [f"{offer.photo};s=640x480"],
		"createdAt": offer.created_at.astimezone(timezone.utc).isoformat(),
	}
