from house import checks


def test_stray_scripts():
    assert checks.stray_scripts("except where теплопод blocks") and not checks.stray_scripts("ジャガ芋 potato")


def test_omission_guard_uses_the_texts_own_baseline():
    ja = "あ" * 100
    pairs = {f"p{i}": (ja, "x" * 300) for i in range(6)}
    pairs["p9"] = (ja, "x" * 100)
    assert list(checks.omissions(pairs)) == ["p9"]
