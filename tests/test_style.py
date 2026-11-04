from types import SimpleNamespace

from house.checks import style


def test_the_house_style_makes_the_mechanical_choices():
    assert style.house_style("“Hi,” he said -- the color——blue. Traveled.", "x") == '"Hi," he said — the colour—blue. Travelled.'
    assert style.house_style("........", "「…………」") == '"…"'
    assert style.house_style(".........\nComplaints rose.", "「………」猫八も") == '"…" Complaints rose.'


def test_readings_are_romanised_in_hepburn():
    assert [style.romaji(k) for k in ("いきなわ", "あんば", "おおすぎ", "りゅうじろう", "がっこう", "しいづかした")] == \
        ["ikinawa", "anba", "ōsugi", "ryūjirō", "gakkō", "shiizukashita"]


def test_a_name_the_english_misread_against_its_ruby_is_listed():
    ruby = {"t": "ruby", "base": [{"s": "生縄"}], "reading": "いきなわ"}
    p = SimpleNamespace(id="p6", tokens=[{"t": "text", "s": "　"}, ruby, {"t": "text", "s": "のお鉄"}])
    bible = {"cast": [{"name_ja": "生縄のお鉄", "reading": "いきなわのおてつ", "romanised": "Ikina no O-Tetsu"}]}
    out = style.readings([p], bible, "Ikina no O-Tetsu was there. Ikina laughed.")
    assert out[0].startswith("生縄《いきなわ》 reads Ikinawa; the English has Ikina ×2")
    assert "Ikina no O-Tetsu" in out[1]
    assert style.readings([p], {"cast": []}, "Ikinawa no O-Tetsu was there.") == []


def test_a_near_form_the_bible_gives_for_another_word_is_not_listed():
    # 東屋《あずまや》 is an arbour; Umeya, close to it in spelling, is the inn 梅屋, as the style sheet says
    ruby = {"t": "ruby", "base": [{"s": "東屋"}], "reading": "あずまや"}
    p = SimpleNamespace(id="p9", tokens=[ruby, {"t": "text", "s": "あり"}])
    english = "They stayed at the Umeya. The Umeya was quiet."
    assert style.readings([p], {"cast": []}, english)[0].startswith("東屋《あずまや》 reads Azumaya; the English has Umeya ×2")
    assert style.readings([p], {"cast": [], "style": "Keep realia: 梅屋 (Umeya), 官報 (Official Gazette)"}, english) == []


def test_words_spelled_more_than_one_way_are_listed_but_not_capitals():
    units = {("p1",): "Ryūjirō ran. *Sensei* said.", ("p2",): "Ryujiro laughed. Sensei nodded. The end.", ("p3",): "the end"}
    lines = style.variants(units, lambda u: u[0])
    assert any("Ryūjirō ×1 (p1)" in l and "Ryujiro ×1 (p2)" in l for l in lines)
    assert any("*Sensei*" in l for l in lines)
    assert not any("end" in l.lower() for l in lines)
