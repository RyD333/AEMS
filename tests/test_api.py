"""Tests run without the real model: llama_cpp.Llama is replaced by a fake."""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import llama_cpp  # noqa: F401
except ImportError:  # dev machine without llama-cpp-python
    stub = types.ModuleType("llama_cpp")
    stub.Llama = object
    sys.modules["llama_cpp"] = stub

import pytest
from fastapi.testclient import TestClient

import app as app_module

GOOD = {
    "Particulars": "4.3 Manage Holiday Calendar", "Complexity": "Average", "OS Operation": "Add",
    "IsASP": 1, "IsSQL": 1, "IsPHP": 0, "IsAndroid": 0, "IsIOS": 0, "IsUI": 1, "IsApplicable": 1,
    "IlfRet": 1, "IlfDataElements": ["HolidayID", "HolidayName", "HolidayDate"],
    "EiRet": 1, "EiDataElements": ["Holiday Name", "Holiday Date", "Action: Save", "Message"],
    "EqRet": 1, "EqDataElements": ["@RETURNMSG"],
    "EifRet": 0, "EifDet": 0, "EoRet": 0, "EoDet": 0,
}

PAYLOAD = {
    "use_case_name": "4.3 Manage Holiday Calendar", "operation": "Add",
    "description": "Add a holiday.", "actors": "HR Administrator",
    "basic_flow": "1. Open form.\n2. Save.", "alternate_flow": "",
}


class FakeLlama:
    mode = "good"

    def __init__(self, **kwargs):
        pass

    def tokenize(self, data, add_bos=True, special=False):
        return list(range(len(data) // 4))

    def __call__(self, tokens, **kwargs):
        if FakeLlama.mode == "garbage":
            text = "this is not json at all"
        else:
            # first object, then a repeated copy - the API must ignore the repeat
            text = json.dumps(GOOD) + json.dumps(GOOD)
        for i in range(0, len(text), 25):
            yield {"choices": [{"text": text[i:i + 25]}]}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_module, "Llama", FakeLlama)
    FakeLlama.mode = "good"
    with TestClient(app_module.app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["model_loaded"] is True


def test_analyze_ok(client):
    r = client.post("/analyze", json={**PAYLOAD, "fpid": 7})
    assert r.status_code == 200
    m = r.json()["metrics"]
    assert m["FPID"] == 7
    assert m["Multiplier"] == 10 and m["Result"] == 10          # from Complexity=Average
    assert (m["IlfDet"], m["EiDet"], m["EqDet"]) == (3, 4, 1)   # list lengths


def test_missing_field_is_422(client):
    bad = dict(PAYLOAD)
    del bad["actors"]
    assert client.post("/analyze", json=bad).status_code == 422


def test_too_long_is_413(client):
    big = {**PAYLOAD, "basic_flow": "x" * 40000}
    assert client.post("/analyze", json=big).status_code == 413


def test_unparseable_output_is_502(client):
    FakeLlama.mode = "garbage"
    assert client.post("/analyze", json=PAYLOAD).status_code == 502
