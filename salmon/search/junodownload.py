import re

from salmon import config
from salmon.errors import ScrapeError
from salmon.search.base import IdentData, SearchMixin
from salmon.sources import JunodownloadBase


class Searcher(JunodownloadBase, SearchMixin):
    async def search_releases(self, searchstr, limit):
        releases = {}
        soup = await self.create_soup(
            self.search_url,
            params={
                "submit-search": "SEARCH",
                "solrorder": "relevancy",
                "q[all][]": [searchstr],
            },
            allow_redirects=False,
        )
        for meta in soup.select(
            "#page_nav + .product-list .productlist_widget_product_detail"
        ):
            try:
                header_type = meta.select("div.productlist_widget_product_info")[0][
                    "ua_location"
                ]
                if header_type != "release header":  # Fuck sample packs, etc.
                    continue

                su_title = meta.select(
                    ".productlist_widget_product_title .jq_highlight.pwrtext a"
                )[0]
                rls_id = re.search(r"/products/[^/]+/([\d-]+)", su_title["href"])[1]
                title = su_title.string

                date = meta.select(".productlist_widget_product_preview_buy span")[
                    0
                ].string
                year = 2000 + int(date[-2:])

                ar_li = [
                    a.string.title()
                    for a in meta.select(
                        ".productlist_widget_product_artists .jq_highlight.pwrtext a"
                    )
                    if a.string
                ]
                artists = (
                    ", ".join(ar_li)
                    if ar_li and len(ar_li) < 5
                    else config.VARIOUS_ARTIST_WORD
                )

                label = meta.select(
                    ".productlist_widget_product_label .jq_highlight.pwrtext a"
                )[0].string.strip()
                catno = (
                    meta.select(".productlist_widget_product_preview_buy")[0]
                    .text.split("\n")[1]
                    .strip()
                )

                if label.lower() not in config.SEARCH_EXCLUDED_LABELS:
                    releases[rls_id] = (
                        IdentData(artists, title, year, None, "WEB"),
                        self.format_result(artists, title, f"{year} {label} {catno}"),
                    )
            except (TypeError, IndexError) as e:
                raise ScrapeError("Failed to parse scraped search results.") from e
            if len(releases) == limit:
                break
        return "Junodownload", releases
