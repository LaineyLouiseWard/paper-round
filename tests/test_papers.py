from paperround.papers import Paper, drop_seen, find_doi, normalise_title


def test_doi_from_doi_org_link():
    assert find_doi("https://doi.org/10.1175/JCLI-D-26-0167.1") == "10.1175/jcli-d-26-0167.1"


def test_doi_from_publisher_links_drops_query():
    assert find_doi("https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2026GL122178?af=R") == "10.1029/2026gl122178"
    assert find_doi("https://iopscience.iop.org/article/10.1088/1748-9326/aead01") == "10.1088/1748-9326/aead01"


def test_doi_from_feed_field_wins_over_link():
    assert find_doi("doi:10.5194/hess-30-6481-2026", "https://hess.copernicus.org/articles/30/6481/2026/") \
        == "10.5194/hess-30-6481-2026"


def test_no_doi():
    assert find_doi("https://hess.copernicus.org/articles/30/6481/2026/", None, "") is None


def test_keys_include_title_doi_and_arxiv():
    p = Paper("A Study: of Rain!", "https://arxiv.org/abs/2610.20519v1", "arXiv", doi="10.1/x")
    assert p.keys() == {"a study of rain", "doi:10.1/x", "arxiv:2610.20519"}


def test_title_form_matches_old_seen_file():
    assert normalise_title("Drought–flood: abrupt alternation?") == "droughtflood abrupt alternation"


def test_drop_seen_by_any_id_and_within_batch():
    seen = {"doi:10.1/old"}
    a = Paper("Old paper new title", "https://doi.org/10.1/old", "J", doi="10.1/old")
    b = Paper("Same paper", "https://x.org/1", "J1")
    c = Paper("Same  paper", "https://y.org/2", "J2")  # same title from a second feed
    d = Paper("Preprint", "https://arxiv.org/abs/2601.00001", "arXiv")
    e = Paper("Preprint, published", "https://doi.org/10.1/p", "J", doi="10.1/p")
    assert [p.link for p in drop_seen([a, b, c, d, e], seen)] == ["https://x.org/1", "https://arxiv.org/abs/2601.00001",
                                                                 "https://doi.org/10.1/p"]
