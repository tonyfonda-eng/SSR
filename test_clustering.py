from monitor import cluster_articles
import json

def test():
    articles = [
        {
            "source_name": "PR Newswire",
            "article_id": "111",
            "title": "Inno Holdings Inc. Announces Resumption of Trading on Nasdaq",
            "body": "AUSTIN, Texas, April 10, 2024 /PRNewswire/ -- Inno Holdings Inc. (Nasdaq: INHD) today announced that Nasdaq has authorized the resumption of trading of its common stock. The trading halt was initiated on March 15, 2024 pending the release of material news regarding the company's internal accounting audit. The company has now satisfied the requests of Nasdaq and filed its delayed 10-K."
        },
        {
            "source_name": "GlobeNewswire",
            "article_id": "222",
            "title": "Inno Holdings Announces Resumption of Trading on Nasdaq",
            "body": "AUSTIN, Texas, April 10, 2024 (GLOBE NEWSWIRE) -- Inno Holdings Inc. (Nasdaq: INHD) today announced that Nasdaq has authorized the resumption of trading of its common stock."
        },
        {
            "source_name": "BusinessWire",
            "article_id": "333",
            "title": "Totally Unrelated Company Buys Factory",
            "body": "Some other news."
        }
    ]
    
    clusters = cluster_articles(articles)
    
    print(f"Total Clusters: {len(clusters)}")
    for i, cluster in enumerate(clusters):
        print(f"\nCluster {i+1}:")
        for article in cluster:
            print(f"  - [{article['source_name']}] {article['title']} (Body Length: {len(article['body'])})")

if __name__ == "__main__":
    test()
