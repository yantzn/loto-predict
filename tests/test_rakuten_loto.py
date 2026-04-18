from src.infrastructure.rakuten_loto import RakutenLotoClient


def test_parse_latest_loto6_html() -> None:
    html = """
    <html><body>
      <table>
        <tr><td>第2094回 2026/04/16</td><td>3 4 7 11 24 30</td><td>16</td></tr>
        <tr><td>第2093回 2026/04/13</td><td>2 10 21 26 29 38</td><td>12</td></tr>
      </table>
    </body></html>
    """

    client = RakutenLotoClient()
    results = client._parse_results_from_html(html, "loto6", "https://example.com/loto6")

    assert results[0].draw_no == 2094
    assert results[0].draw_date == "2026-04-16"
    assert results[0].main_numbers == [3, 4, 7, 11, 24, 30]
    assert results[0].bonus_numbers == [16]


def test_parse_latest_loto7_html() -> None:
    html = """
    <html><body>
      <table>
        <tr><td>第0673回 2026/04/17</td><td>6 9 10 12 16 24 32</td><td>17 19</td></tr>
      </table>
    </body></html>
    """

    client = RakutenLotoClient()
    results = client._parse_results_from_html(html, "loto7", "https://example.com/loto7")

    assert results[0].draw_no == 673
    assert results[0].draw_date == "2026-04-17"
    assert results[0].main_numbers == [6, 9, 10, 12, 16, 24, 32]
    assert results[0].bonus_numbers == [17, 19]