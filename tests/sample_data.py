# 実際の Zenn RSS と同じ構造（CDATA、enclosure、guid、dc:creator）
ZENN_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
<title><![CDATA[Zennの「Claude Code」のフィード]]></title>
<link>https://zenn.dev/topics/claudecode</link>
<item>
<title><![CDATA[Claude Code入門]]></title>
<description><![CDATA[はじめに：最初の要約です]]></description>
<link>https://zenn.dev/alice/articles/aaa111</link>
<guid isPermaLink="true">https://zenn.dev/alice/articles/aaa111</guid>
<pubDate>Sat, 31 Oct 2026 09:21:22 GMT</pubDate>
<enclosure url="https://example.com/ogp.png" length="0" type="image/png"/>
<dc:creator><![CDATA[alice]]></dc:creator>
</item>
<item>
<title><![CDATA[フック活用術]]></title>
<description><![CDATA[二番目の要約]]></description>
<link>https://zenn.dev/bob/articles/bbb222</link>
<guid isPermaLink="true">https://zenn.dev/bob/articles/bbb222</guid>
<pubDate>Fri, 30 Oct 2026 00:00:00 GMT</pubDate>
<dc:creator><![CDATA[bob]]></dc:creator>
</item>
</channel>
</rss>"""

# 実際の Qiita Atom と同じ構造（published は +09:00）
QIITA_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="ja-JP" xmlns="http://www.w3.org/2005/Atom">
  <id>tag:qiita.com,2005:/tags/claudecode/feed</id>
  <title>ClaudeCodeタグが付けられた新着記事 - Qiita</title>
  <updated>2026-10-31T18:47:11+09:00</updated>
  <entry>
    <id>tag:qiita.com,2005:PublicArticle/1</id>
    <published>2026-10-31T18:47:11+09:00</published>
    <updated>2026-10-31T18:47:11+09:00</updated>
    <link rel="alternate" type="text/html" href="https://qiita.com/carol/items/ccc333"/>
    <url>https://qiita.com/carol/items/ccc333</url>
    <title>Qiitaの記事</title>
    <content type="text">Qiitaの本文の冒頭</content>
    <author><name>carol</name></author>
  </entry>
</feed>"""


def github_release(**overrides):
    # 実際の GitHub API レスポンスに近い項目を揃える
    release = {
        "id": 1,
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v2.1.316",
        "tag_name": "v2.1.316",
        "name": "v2.1.316",
        "draft": False,
        "prerelease": False,
        "created_at": "2026-10-31T01:01:10Z",
        "published_at": "2026-10-31T01:01:35Z",
        "body": "## What's changed\n\n- Added a flag",
    }
    release.update(overrides)
    return release


