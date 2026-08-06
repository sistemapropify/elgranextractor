from datetime import date

from lead_intelligence.services import get_lead_conversation, get_lead_results

result = get_lead_results(date(2026, 7, 14), date(2026, 7, 14), "qualified")
print("qualified_cards", len(result["leads"]))
if result["leads"]:
    lead = get_lead_conversation(result["leads"][0]["id"])
    print("detail_messages", lead["total_messages"], "ordered", bool(lead["messages"]))
