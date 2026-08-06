from ocr_service.llm_classify import LlmClassifyClient


def test_completion_url_accepts_base_or_full_endpoint():
    client = LlmClassifyClient()
    assert client._completion_url("https://example.com/v1") == "https://example.com/v1/chat/completions"
    assert client._completion_url("https://example.com/v1/chat/completions") == "https://example.com/v1/chat/completions"


def test_parse_json_accepts_markdown_and_trailing_comma():
    result = LlmClassifyClient._parse_json('```json\n{"results":[{"id":"1","category":"其他",}],}\n```')
    assert result["results"][0]["id"] == "1"


def test_large_transaction_list_is_sent_in_batches():
    class Response:
        status_code = 200
        ok = True
        def json(self):
            return {"choices": [{"message": {"content": '{"results":[]}'}}]}

    class Session:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs): self.calls += 1; return Response()

    client = LlmClassifyClient()
    client._session = Session()
    client.classify([{"id": str(i)} for i in range(205)], api_url="https://example.com/v1", api_key="", model="test")
    assert client._session.calls == 3
