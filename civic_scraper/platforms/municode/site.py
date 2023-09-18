# deal with video, POST request, delete useless functions
import datetime
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

import civic_scraper
from civic_scraper import base
from civic_scraper.base.asset import Asset, AssetCollection
from civic_scraper.base.cache import Cache
from civic_scraper.utils import today_local_str

from .parser import Parser

logger = logging.getLogger(__name__)


class Site(base.Site):
    def __init__(self, base_url, cache=Cache(), parser_kls=Parser, place_name=None):
        super().__init__(base_url, cache=cache, parser_kls=parser_kls)
        self.base_url = base_url
        self.subdomain = urlparse(base_url).netloc.split(".")[0]
        self.place_name = place_name
        self.state_or_province = self._get_asset_metadata(
            r"(?<=//)\w{2}(?=-)", base_url
        )

    @property
    def place(self):
        return self.place_name or self._get_asset_metadata(r"(?<=-)\w+(?=\.)", self.base_url)

    def scrape(self,
               start_date=None,
               end_date=None,
               cache=False,
               download=False,
               file_size=None,
               asset_list=None,):
        today = today_local_str()
        start = start_date or today
        end = end_date or today

        response_url = self.url
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
        }
        raw_htmls = []
        page = 0

        while True:
            result = requests.get(self.url + "?page=" + str(page), headers=headers).text
            print(self.url + "?page=" + str(page))
            print(result)
            if "Your browser sent an invalid request." in result:
                print("Being throttled and/or blocked!")
                break
            elif "Meetings Directory" in result:
                raw_htmls.append(result)
                page += 1
            else:
                break
        # Cache the raw html from search results page
        file_metadata = []
        for page in raw_htmls:
            if cache:
                cache_path = (
                    f"{self.cache.artifacts_path}/{self._cache_page_name(response_url)}"
                )
                self.cache.write(cache_path, page)
                logger.info(f"Cached search results page HTML: {cache_path}")
            file_metadata += self.parser_kls(page).parse()

        assets = self._build_asset_collection(file_metadata)
        if download:
            asset_dir = Path(self.cache.path, "assets")
            asset_dir.mkdir(parents=True, exist_ok=True)
            for asset in assets:
                if self._skippable(asset, file_size, asset_list):
                    continue
                asset.download(str(asset_dir))
        return assets

    def _skippable(self, asset, file_size, asset_list):
        if file_size:
            max_bytes = self._mb_to_bytes(file_size)
            if float(asset.content_length) > max_bytes:
                return True
        if asset_list:
            if asset.asset_type in asset_list:
                return True
        return False

    def _cache_page_name(self, response_url):
        return (
            response_url.replace(":", "")
            .replace("//", "__")
            .replace("/", "__")
            .replace("?", "QUERY")
        )

    def _state_or_province(self, url):
        pass

    def _search(self, start_date, end_date):
        params = {
            "term": "",
            "CIDs": "all",
            "startDate": self._convert_date(start_date),
            "endDate": self._convert_date(end_date),
            "dateRange": "",
            "dateSelector": "",
        }
        # Search URLs follow the below pattern
        # /Search/?term=&CIDs=all&startDate=12/17/2020&endDate=12/18/2020&dateRange=&dateSelector=
        search_url = self.url.rstrip("/") + "/Search/"
        response = requests.get(search_url, params=params)
        return response.url, response.text

    def _convert_date(self, date_str):
        if date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y")
        else:
            return None

    def _build_asset_collection(self, metadata):
        """Create assets from metadata

        Args:
            metadata (list) Array of dicts containing asset metadata.

        Returns:
            AssetCollection
        """
        assets = AssetCollection()
        for row in metadata:
            url = self._mk_url(self.url, row["url"])
            asset_args = {
                "state_or_province": self.state_or_province,
                "place": self.place,
                "place_name": self.place_name,
                "committee_name": row["meeting"],
                "meeting_date": row["date"],
                "asset_name": row["asset_type"] + "_" + row["format"],
                "asset_type": row["asset_type"],
                "scraped_by": f"civic-scraper_{civic_scraper.__version__}",
                "url": url,
                "content_type": row["format"],
                "meeting_id": row["url"].replace('/', "").replace('/', "")
            }

            # unable to find content size through header

            print(asset_args)
            # TODO: Add conditional here to short-circuit
            # header request based on method option
            # headers = requests.head(url, allow_redirects=True).headers

            assets.append(Asset(**asset_args))
        return assets

    def _mk_url(self, url, url_path):
        base_url = url.split("/Agenda")[0]
        return urljoin(base_url, url_path)

    def _mk_mtg_id(self, subdomain, raw_mtg_id):
        return f"civicplus_{subdomain}_{raw_mtg_id.lstrip('_')}"

    def _get_asset_metadata(self, regex, asset_link):
        """
        Extracts metadata from a provided asset URL.
        Input: Regex to extract metadata
        Returns: Extracted metadata as a string or "no_data" if no metadata is extracted
        """
        if re.search(regex, asset_link) is not None:
            return re.search(regex, asset_link).group(0)
        else:
            return "no_data"

    def _mb_to_bytes(self, size_mb):
        if size_mb is None:
            return None
        return float(size_mb) * 1048576
