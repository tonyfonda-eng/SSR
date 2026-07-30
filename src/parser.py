from bs4 import BeautifulSoup


def extract_text(html):

    soup = BeautifulSoup(html, "html.parser")

    article = soup.find("div", class_="release-body")

    if article is None:
        return None

    return article.get_text(" ", strip=True)
