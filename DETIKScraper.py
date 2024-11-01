import httpx
import asyncio
import datetime
import pandas as pd
import streamlit as st
from selectolax.parser import HTMLParser
from typing import List, Dict, Union


async def fetch_page(url: str, params: dict, headers: dict) -> Union[str, None]:
    """Fetch a webpage content with error handling."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            return response.text
        except httpx.TimeoutException:
            st.error(f"Timeout: unable to connect to {url}. Please try again.")
            return None
        except httpx.HTTPStatusError as e:
            st.error(f"HTTP error: {str(e)}")
            return None


async def parse_content(url: str) -> str:
    """Extract content from a given URL."""
    html = await fetch_page(url, {}, {})
    # if not html:
    #     return "Error fetching content."

    parser = HTMLParser(html)
    paragraphs = [p.text() for p in parser.css('div.detail__body-text > p')]
    return "\n".join(paragraphs) if paragraphs else "No content available."


async def parse_item(result) -> Dict[str, str]:
    """Extract information from a single search result."""
    title = result.css_first('h3.media__title').text()
    date = result.css_first('.media__date > span').attrs['title']
    url = result.css_first('a').attrs['href']
    desc_element = result.css_first('div.media__desc')
    desc = desc_element.text() if desc_element else "No description"

    # Fetch content for each item
    content = await parse_content(url)

    return {
        'title': title,
        'url': url,
        'date': date,
        'desc': desc,
        'content': content
    }


async def parse(url: str, params: dict, headers: dict) -> List[Dict[str, str]]:
    """Parse search results from the page and extract details."""
    html = await fetch_page(url, params, headers)
    if not html:
        return []

    parser = HTMLParser(html)
    search_results = parser.css('article')

    # Parse each result concurrently
    return await asyncio.gather(*[parse_item(result) for result in search_results])


async def fetch_json(url: str, headers: dict = None) -> Union[Dict, None]:
    """Fetch JSON data from the provided URL with error handling."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            return response.json()
        except httpx.TimeoutException:
            st.error(f"Timeout: unable to connect to {url}. Please try again.")
            return None
        except httpx.HTTPStatusError as e:
            st.error(f"HTTP error: {str(e)}")
            return None


async def get_trending_keywords(api_url: str, headers: dict) -> List[str]:
    """Retrieve trending keywords from the API."""
    json_data = await fetch_json(api_url, headers)
    if not json_data or 'body' not in json_data or 'topKeywordSearch' not in json_data['body']:
        return []

    # Extract keywords from the 'topKeywordSearch' section of the JSON response
    trending_keywords = [item['keyword'] for item in json_data['body']['topKeywordSearch']]
    return trending_keywords


async def main():
    """Main Streamlit application function."""
    search_url = "https://www.detik.com/search/searchall?"
    trending_api_url = "https://explore-api.detik.com/trending"  # API for trending keywords

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/244.178.44.111 Safari/537.36",
    }

    # Streamlit container to group the input elements
    with st.container():
        st.title("DETIKScraper")

        # Fetch and display trending keywords from the API
        with st.spinner("Fetching trending keywords..."):
            trending_keywords = await get_trending_keywords(trending_api_url, headers)

        if trending_keywords:
            st.subheader("Trending Search Keywords:")
            st.write(", ".join(trending_keywords))
        else:
            st.write("No trending keywords found.")

        keyword = st.text_input("Search keyword")

        # Total pages and export options
        pages = int(st.text_input("Total Pages", value="1"))
        export_format = st.selectbox("Export to", ["CSV", "XLSX", "JSON"])

        # Disable Scrape button when keyword is empty
        scrape_button = st.button("Scrape", disabled=not keyword)

    if scrape_button and keyword:
        with st.spinner(f"Scraping results for '{keyword}'..."):
            now = datetime.datetime.now()
            formatted_time = now.strftime("%Y%m%d_%H%M%S")

            params = {
                "query": keyword,
                "page": 1,  # Placeholder, will be adjusted in loop
            }

            # Collect data for all pages asynchronously
            all_items = []
            for page in range(1, pages + 1):
                params['page'] = page
                items = await parse(search_url, params, headers)
                all_items.extend(items)

            if all_items:
                data = pd.DataFrame(all_items)
                data.index += 1
                st.dataframe(data)

                file_name = f"{formatted_time}_{keyword}_{pages}.{export_format.lower()}"
                
                if export_format == "CSV":
                    csv_data = data.to_csv(index=False)
                    st.download_button("Download CSV", data=csv_data, file_name=file_name, mime="text/csv")
                elif export_format == "XLSX":
                    xlsx_data = data.to_excel(index=False, engine='openpyxl')
                    st.download_button("Download XLSX", data=xlsx_data, file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else:  # JSON
                    json_data = data.to_json(orient='records')
                    st.download_button("Download JSON", data=json_data, file_name=file_name, mime="application/json")
                
                st.success("Scraping completed!")
            else:
                st.error("No data scraped.")


if __name__ == '__main__':
    asyncio.run(main())
