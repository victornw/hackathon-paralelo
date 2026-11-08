from app.web.acordado import url_publica


def test_so_liga_no_render(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    assert url_publica() is None
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://exemplo.onrender.com/")
    assert url_publica() == "https://exemplo.onrender.com/saude"
    monkeypatch.setenv("MANTER_ACORDADO", "0")
    assert url_publica() is None
