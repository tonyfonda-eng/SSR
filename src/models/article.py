from dataclasses import dataclass


@dataclass
class Article:
    source: str
    article_id: str
    title: str
    url: str
    published: str
    body: str
