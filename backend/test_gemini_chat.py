import json
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.chatbot.gemini_client import clean_json_markdown
from app.chatbot.intent_classifier import set_tier2_test_provider

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def run_tests():
    print("=== 1. Test clean_json_markdown ===")
    sample_markdown = '```json\n{"intent": "SHOW_FLAGGED", "invoice_id": null}\n```'
    cleaned = clean_json_markdown(sample_markdown)
    print("Cleaned JSON string:", cleaned)
    parsed = json.loads(cleaned)
    assert parsed["intent"] == "SHOW_FLAGGED"
    print("clean_json_markdown passed successfully!\n")

    client = TestClient(app)

    print("=== 2. Test TIER 1 (Exact rules) ===")
    t1_res = client.post("/api/chat", json={"message": "show flagged invoices"})
    print("Status:", t1_res.status_code)
    data1 = t1_res.json()
    print("Tier:", data1.get("tier"), "| Intent:", data1.get("intent"))
    print("Reply:", data1.get("reply")[:100], "...\n")
    assert data1.get("tier") == 1

    print("=== 3. Test TIER 2 with dummy key (Graceful Fallback without crash) ===")
    t2_fallback = client.post("/api/chat", json={"message": "tell me a joke about accounting"})
    print("Status:", t2_fallback.status_code)
    data2 = t2_fallback.json()
    print("Tier:", data2.get("tier"), "| Intent:", data2.get("intent"))
    print("Reply excerpt:", data2.get("reply")[:120], "...\n")
    assert data2.get("tier") == 2
    assert t2_fallback.status_code == 200

    print("=== 4. Test TIER 2 Natural Language with Gemini Output ===")
    def mock_gemini_output(msg: str):
        if "stuck" in msg.lower():
            return '```json\n{"intent": "SHOW_FLAGGED", "invoice_id": null}\n```'
        elif "today" in msg.lower():
            return '```json\n{"intent": "SHOW_STATS", "invoice_id": null}\n```'
        elif "sign off" in msg.lower():
            return '```json\n{"intent": "APPROVE_INVOICE", "invoice_id": "INV-1002"}\n```'
        return None

    set_tier2_test_provider(mock_gemini_output)

    test_queries = [
        "can you tell me which invoices got stuck",
        "what's going on with the invoices today",
        "I want to sign off on INV-1002",
    ]

    results = []
    for q in test_queries:
        res = client.post("/api/chat", json={"message": q})
        assert res.status_code == 200
        body = res.json()
        results.append({
            "query": q,
            "tier": body.get("tier"),
            "intent": body.get("intent"),
            "reply": body.get("reply"),
            "data": body.get("data")
        })
        print(f"Query: \"{q}\"")
        print(f"Tier: TIER {body.get('tier')} (LLM Fallback)")
        print(f"Intent: {body.get('intent')}")
        print(f"Reply: {body.get('reply')[:150]}...")
        if body.get("data"):
            keys = list(body.get("data").keys())
            print(f"Structured Data Keys: {keys}")
        print("-" * 50)

    print("\nAll chatbot tests completed successfully!")

if __name__ == "__main__":
    run_tests()
