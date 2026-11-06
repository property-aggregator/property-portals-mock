"""Testy samego mocka: czy zwraca strony w formacie, którego oczekuje scraper.

Nie testują scrapera. Opcjonalny test zgodności uruchamia się tylko wtedy,
gdy ustawisz SCRAPER_SRC na katalog `scraper/src` z repozytorium scrapera.
"""
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app import PortalServer  # noqa: E402
from server.data import build_offers  # noqa: E402

OLX_PATH = ("/nieruchomosci/mieszkania/sprzedaz/mazowieckie/"
            "?search%5Bfilter_float_price%3Afrom%5D=0&search%5Bfilter_float_price%3Ato%5D=50000000")
OTODOM_PATH = "/pl/wyniki/sprzedaz/mieszkanie,rynek-wtorny/cala-polska?limit=72&ownerTypeSingleSelect=ALL"
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


@pytest.fixture
def make_portal():
	servers = []

	def start(scenario: str = "normal") -> str:
		server = PortalServer(("127.0.0.1", 0), scenario)
		servers.append(server)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		return f"http://127.0.0.1:{server.server_address[1]}"

	yield start
	for server in servers:
		server.shutdown()
		server.server_close()


def fetch(base: str, path: str) -> str:
	with urllib.request.urlopen(base + path) as response:
		return response.read().decode("utf-8")


def olx_state(html: str) -> dict:
	marker = "__PRERENDERED_STATE__="
	start = html.index(marker) + len(marker)
	raw, _ = json.JSONDecoder().raw_decode(html[start:].lstrip())
	return raw["listing"]["listing"]


def otodom_search_ads(html: str) -> dict:
	match = NEXT_DATA.search(html)
	return json.loads(match.group(1))["props"]["pageProps"]["data"]["searchAds"]


def test_olx_page_has_cards_pagination_and_state(make_portal):
	html = fetch(make_portal(), OLX_PATH)
	assert html.count('data-testid="l-card"') == 40
	assert 'data-testid="pagination-forward"' in html
	state = olx_state(html)
	assert state["pageNumber"] == 0
	assert state["totalElements"] == 1000  # ucinane do 1000, jak w prawdziwym OLX
	assert state["totalPages"] == 25  # max 25 stron na zapytanie


def test_olx_contains_links_to_otodom_that_scraper_skips(make_portal):
	base = make_portal()
	external = sum(
		fetch(base, OLX_PATH + f"&page={page}").count('href="https://www.otodom.pl/')
		for page in range(1, 6))
	assert external > 0


def test_otodom_page_has_next_data_with_pagination(make_portal):
	ads = otodom_search_ads(fetch(make_portal(), OTODOM_PATH))
	assert ads["pagination"]["currentPage"] == 1
	assert ads["pagination"]["totalPages"] == 36  # 2570 ofert po 72 na stronę
	assert len(ads["items"]) == 72


def test_otodom_past_last_page_serves_page_one(make_portal):
	ads = otodom_search_ads(fetch(make_portal(), OTODOM_PATH + "&page=999"))
	assert ads["pagination"]["currentPage"] == 1  # jak w prawdziwym Otodom


def test_dataset_is_deterministic():
	first = [o.code for o in build_offers()]
	second = [o.code for o in build_offers()]
	assert first == second
	assert len(first) == len(set(first))


def test_scenario_empty_returns_no_offers(make_portal):
	base = make_portal("empty")
	assert olx_state(fetch(base, OLX_PATH))["totalElements"] == 0
	assert 'data-testid="l-card"' not in fetch(base, OLX_PATH)
	assert otodom_search_ads(fetch(base, OTODOM_PATH))["items"] == []


def test_scenario_layout_change_removes_markers(make_portal):
	base = make_portal("layout_change")
	assert 'data-testid="l-card"' not in fetch(base, OLX_PATH)
	assert NEXT_DATA.search(fetch(base, OTODOM_PATH)) is None


def test_scenario_no_state_omits_prerendered_state(make_portal):
	html = fetch(make_portal("no_state"), OLX_PATH)
	assert "__PRERENDERED_STATE__=" not in html
	assert 'data-testid="l-card"' in html


def test_scenario_server_error_fails_page_two(make_portal):
	base = make_portal("server_error")
	with pytest.raises(urllib.error.HTTPError) as error:
		fetch(base, OLX_PATH + "&page=2")
	assert error.value.code == 500


def test_scenario_rate_limit_throttles_every_third_request(make_portal):
	base = make_portal("rate_limit")
	statuses = []
	for _ in range(3):
		try:
			fetch(base, OTODOM_PATH)
			statuses.append(200)
		except urllib.error.HTTPError as error:
			statuses.append(error.code)
	assert statuses == [200, 200, 429]


SCRAPER_SRC = os.environ.get("SCRAPER_SRC")


@pytest.mark.skipif(not SCRAPER_SRC, reason="ustaw SCRAPER_SRC na katalog scraper/src")
def test_real_scraper_parses_mock_pages(make_portal):
	for key, value in {
		"RABBITMQ_HOST": "localhost", "RABBITMQ_USER": "guest", "RABBITMQ_PASSWORD": "guest",
		"REQUEST_DELAY": "0.01", "REQUEST_TIMEOUT": "10", "FIRST_PAGE_INTERVAL": "10",
		"FULL_SCRAPE_TIME": "02:00",
	}.items():
		os.environ.setdefault(key, value)
	sys.path.insert(0, SCRAPER_SRC)
	from property_scraper.scrapers.olx_scraper import OlxScraper
	from property_scraper.scrapers.otodom_scraper import OtodomScraper

	base = make_portal()
	olx = OlxScraper.__new__(OlxScraper)
	olx_result = olx.parse_listing_page(fetch(base, OLX_PATH), page_number=1, scrape_type="FULL")
	assert len(olx_result.offers) == 40
	assert all(offer.source_id.startswith("ID") for offer in olx_result.offers)

	otodom = OtodomScraper.__new__(OtodomScraper)
	otodom_result = otodom.parse_listing_page(fetch(base, OTODOM_PATH), page_number=1, scrape_type="FULL")
	assert len(otodom_result.offers) == 72
