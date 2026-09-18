from pathlib import Path

import pytest

from scripts.yemen_geography_import import load_rows, validate_rows


def write_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "geography.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_valid_yemen_hierarchy_is_accepted(tmp_path):
    path = write_csv(tmp_path, """code,level,name,name_ar,parent_code,status,metadata_json
YE,country,Yemen,اليمن,,active,{}
YE-ADN,governorate,Aden,عدن,YE,active,{}
YE-ADN-01,district,Mansoura,المنصورة,YE-ADN,active,{"source":"reviewed"}
YE-ADN-01-01,locality,Example,مثال,YE-ADN-01,active,{}
""")
    rows = load_rows(path)
    validate_rows(rows)
    assert len(rows) == 4


def test_cross_level_parent_is_rejected(tmp_path):
    path = write_csv(tmp_path, """code,level,name,name_ar,parent_code,status,metadata_json
YE,country,Yemen,اليمن,,active,{}
YE-ADN,governorate,Aden,عدن,YE,active,{}
YE-X,district,Wrong,خطأ,YE,active,{}
""")
    with pytest.raises(ValueError, match="must be level governorate"):
        validate_rows(load_rows(path))


def test_duplicate_codes_are_rejected(tmp_path):
    path = write_csv(tmp_path, """code,level,name,name_ar,parent_code,status,metadata_json
YE,country,Yemen,اليمن,,active,{}
YE-ADN,governorate,Aden,عدن,YE,active,{}
YE-ADN,governorate,Aden 2,عدن 2,YE,active,{}
""")
    with pytest.raises(ValueError, match="duplicate geography code"):
        validate_rows(load_rows(path))
