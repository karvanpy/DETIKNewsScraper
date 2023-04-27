import httpx
import asyncio
import datetime
import pandas as pd
import streamlit as st
from selectolax.parser import HTMLParser

async def parse_item(result):
    # Extract the title and URL of each search result item
    title = result.css_first('h2').text()
    url = result.css_first('a').attrs['href']
    category = result.css_first('span.category').text()
    date = result.css_first('span.date').text().lstrip(category)
    desc = result.css_first('span.box_text > p').text()
    return {
        'title': title,
        'url': url,
        'category': category,
        'date': date,
        'desc': desc
    }

async def parse(url, params, headers):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
        except httpx.TimeoutException:
            st.error(f"Sorry, unable to connect to {url}. \nPlease try again.")
            return

    parser = HTMLParser(response.text)

    # Extract the search result items from the HTML
    search_results = parser.css('article')

    # Extract the items in parallel using map and asyncio.gather
    items = await asyncio.gather(*[parse_item(result) for result in search_results])
    return items


async def main():
    url = "https://www.detik.com/search/searchall?"

    st.title("DETIKScraper")

    keyword = st.text_input("Search keyword")
    pages = int(st.text_input("Total Pages", value="1"))
    options = st.selectbox("Export to", ["CSV", "XLSX", "JSON"])

    
    if st.button("Scrape"):
        # Get the current date and time
        now = datetime.datetime.now()
        # Format the current date and time as a string
        formatted_date_time = now.strftime("%Y%m%d_%H%M%S")

        params = {
            "query": keyword,
            "page": pages,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/244.178.44.111 Safari/537.36",
        }

        # Scrape the first `pages` pages of search results asynchronously using map and asyncio.gather
        items = await asyncio.gather(*[parse(url, {**params, 'page': page}, headers) for page in range(1, pages + 1)])

        # Flatten the nested list of items
        items = [item for page_items in items for item in page_items]
        print(items)

        data = pd.DataFrame(items)
        data.index += 1

        st.dataframe(data)

        mime_types = {
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "json": "application/json",
        }
        mime_type = mime_types.get(options.lower())
        file_name = f"{formatted_date_time}_{keyword}_{pages}.{options.lower()}"
        st.download_button("Download Result", data=data.to_csv(index=False), file_name=file_name, mime=mime_type)



if __name__ == '__main__':
    asyncio.run(main())
