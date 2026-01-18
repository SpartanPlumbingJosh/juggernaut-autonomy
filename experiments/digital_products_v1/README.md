# Experiment: Digital Products v1

## Product: AI Automation Prompt Pack for Small Business

**Status:** Ready for launch  
**Platform:** Gumroad  
**Price:** $9 (recommended)  
**Opportunity ID:** de2ca988-1230-41f2-a4c1-b18da3dadb75

## Files
- `ai-automation-prompt-pack.pdf` - The product (30 prompts)
- `gumroad-listing.md` - Listing copy and launch instructions

## Hypothesis
Small business owners will pay $7-12 for curated, ready-to-use AI prompts that save them time on common tasks.

## Success Criteria
- 10+ sales in first 30 days = validated
- <5 sales = pivot or kill

## Tracking
Revenue tracked via `record_revenue()` function with attribution:
```python
record_revenue(
    event_type="sale",
    gross_amount=9.00,
    net_amount=8.10,  # After Gumroad 10% fee
    source="gumroad",
    description="AI Automation Prompt Pack sale",
    attribution={"experiment": "digital_products_v1", "product": "prompt_pack_v1"}
)
```

## Timeline
- Created: 2026-01-18
- Launched: [PENDING]
- First sale: [PENDING]
