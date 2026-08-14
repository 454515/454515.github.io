"""Stage 3 self-test: verify IDCardProcessor field extraction (spec-03 §7).

Checks:
1. Standard three-field OCR words -> all three fields extracted.
2. Trailing lowercase x in the ID number -> normalized to uppercase X.
3. Missing name/gender -> recorded in `missing`, no exception.
4. Vertical-layout words -> still extracted.
5. Accuracy over a generated 20-sample set >= 98% (spec-03 §6).
6. Registry can register / fetch a processor.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_idcard_processor.py
"""
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ocr.models import OcrResult, OcrWord  # noqa: E402
from src.processors import (  # noqa: E402
    IDCardProcessor,
    get_processor,
    register_processor,
    registered_types,
)
from src.processors.idcard import validate_id_number  # noqa: E402

NAMES = ["张伟", "李娜", "王芳", "刘洋", "陈静", "杨帆", "赵磊", "黄敏", "周杰", "吴倩"]


def make_word(text: str, x: int, y: int, w: int = 80, h: int = 30,
              conf: float = 0.98) -> OcrWord:
    return OcrWord(
        text=text,
        confidence=conf,
        box=[[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
    )


def make_id_words(name: str, gender: str, id_no: str, *,
                  vertical: bool = False, same_block: bool = False) -> list[OcrWord]:
    """Build a realistic ID-card OCR word set for the given layout."""
    words = []
    if vertical:
        words.append(make_word("姓名", 100, 60))
        words.append(make_word(name, 100, 110))
        words.append(make_word("性别", 100, 170))
        words.append(make_word(gender, 100, 220))
        words.append(make_word("公民身份号码", 100, 280))
        words.append(make_word(id_no, 100, 340))
    else:
        if same_block:
            words.append(make_word(f"姓名 {name}", 100, 60))
            words.append(make_word(f"性别 {gender} 民族 汉", 100, 120))
        else:
            words.append(make_word("姓名", 100, 60))
            words.append(make_word(name, 180, 60))
            words.append(make_word("性别", 100, 120))
            words.append(make_word(gender, 180, 120))
        words.append(make_word("公民身份号码", 100, 180))
        words.append(make_word(id_no, 100, 240))
    return words


def _check(result, name, gender, id_no, label: str) -> None:
    expected = {"name": name, "gender": gender, "id_number": id_no}
    assert result.fields == expected, f"{label}: fields={result.fields}"
    assert result.missing == [], f"{label}: missing={result.missing}"
    print(f"[ok] {label}")


def main() -> int:
    proc = IDCardProcessor()

    # 1. Standard three fields, label/value split horizontally
    id_no = "321322200406170832"
    r = proc.process(OcrResult(words=make_id_words("张建邺", "男", id_no)))
    _check(r, "张建邺", "男", id_no, "standard horizontal")

    # 2. Trailing lowercase x -> uppercase X (also label+value same block)
    id_x = "32132220040617083x"
    r = proc.process(OcrResult(
        words=make_id_words("张建邺", "男", id_x, same_block=True)))
    _check(r, "张建邺", "男", "32132220040617083X", "lowercase x normalized")

    # 3. Missing name/gender: recorded, no crash
    words = [
        make_word("性别", 100, 60), make_word("男", 180, 60),
        make_word("公民身份号码", 100, 120), make_word("321322200406170832", 100, 180),
    ]
    r = proc.process(OcrResult(words=words))
    assert "name" in r.missing and "gender" not in r.missing, r.missing
    assert r.fields["gender"] == "男" and r.fields["id_number"] == "321322200406170832"
    print(f"[ok] missing name recorded: {r.missing}")

    # 4. Vertical layout
    r = proc.process(OcrResult(words=make_id_words("张建邺", "女", id_no, vertical=True)))
    _check(r, "张建邺", "女", id_no, "vertical layout")

    # 5. Accuracy over 20 generated samples (spec-03 §6, need >= 98%)
    rng = random.Random(42)
    layouts = ["h_sep", "h_same", "v"]
    correct = 0
    failures = []
    for i in range(20):
        name = rng.choice(NAMES)
        gender = rng.choice(["男", "女"])
        id_no = f"{rng.randint(10 ** 16, 10 ** 17 - 1)}{rng.choice('0123456789xX')}"
        layout = rng.choice(layouts)
        words = make_id_words(
            name, gender, id_no,
            vertical=(layout == "v"), same_block=(layout == "h_same"),
        )
        r = proc.process(OcrResult(words=words))
        expected = {"name": name, "gender": gender,
                    "id_number": id_no[:-1] + id_no[-1].upper()}
        if r.fields == expected and r.missing == []:
            correct += 1
        else:
            failures.append((i, layout, expected, r.fields, r.missing))
    rate = correct / 20
    print(f"[ok] accuracy={rate:.2%} ({correct}/20)")
    for f in failures:
        print("  FAIL:", f)
    assert rate >= 0.98, f"accuracy {rate:.2%} < 98%"

    # 6. Registry
    assert get_processor("idcard") is not None
    assert "idcard" in registered_types()
    class _Dummy(IDCardProcessor):
        pass
    register_processor("dummy", _Dummy())
    assert "dummy" in registered_types()
    print("[ok] registry register/get")

    # 7. validate_id_number
    assert validate_id_number("321322200406170832") is True
    assert validate_id_number("32132220040617083X") is True
    assert validate_id_number("123") is False
    assert validate_id_number("32132220040617083x") is False  # lowercase x invalid
    print("[ok] validate_id_number")

    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
