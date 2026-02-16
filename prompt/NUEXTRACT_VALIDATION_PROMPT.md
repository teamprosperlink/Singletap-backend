# VRIDDHI JSON Validation Schema

You are a JSON validator. Validate and correct the JSON structure below.

## REQUIRED FIELDS

| Field | Type | Allowed Values |
|-------|------|----------------|
| intent | string | "product", "service", "mutual" |
| subintent | string | Depends on intent (see below) |
| domain | array | From allowed domains list |
| items | array | Objects with type, categorical, min, max, range |

### Subintent Rules
- intent="product" → subintent: "buy" or "sell"
- intent="service" → subintent: "seek" or "provide"
- intent="mutual" → subintent: "connect"

## ALLOWED DOMAINS (lowercase with &)

### Product Domains (21)
technology & electronics, healthcare & wellness, fashion & apparel, home & furniture, food & beverage, automotive & vehicles, sports & outdoors, office & stationery, books media & entertainment, pets & animals, real estate & property, manufacturing & production, agriculture & farming, environmental & sustainability, textile & clothing manufacturing, jewelry & accessories manufacturing, beauty & cosmetics, handicrafts & artisan products, energy & utilities, security & safety, mining & quarrying

### Service Domains (18)
education & training, finance insurance & legal, transportation & logistics, hospitality travel & accommodation, business services & consulting, marketing advertising & design, construction & trades, entertainment & events, personal services, government & regulatory, utilities & infrastructure, telecommunication & internet, nonprofit & charity services, repair & maintenance services, customs & culture services, alternative & holistic health, research & development, government & public administration

### Mutual Categories (25)
housing, roommates, fitness, sports, partners, travel, adventure, learning, study, professional, career, social, friendship, dating, relationships, parenting, family, hobbies, interests, pets, animals, support, caregiving, community, volunteering

## JSON STRUCTURE

```json
{
  "intent": "product|service|mutual",
  "subintent": "buy|sell|seek|provide|connect",
  "domain": ["lowercase domain with &"],
  "items": [
    {
      "type": "market noun (laptop, plumbing, etc.)",
      "categorical": {"brand": "value", "color": "value"},
      "min": {
        "cost": [{"type": "price", "value": 1000, "unit": "INR"}],
        "capacity": [{"type": "storage", "value": 256, "unit": "gb"}]
      },
      "max": {
        "cost": [{"type": "price", "value": 50000, "unit": "INR"}]
      },
      "range": {
        "cost": [{"type": "price", "min": 40000, "max": 60000, "unit": "INR"}]
      }
    }
  ],
  "target_location": {"name": "city_name"} or {},
  "location_match_mode": "near_me|explicit|target_only|route|global",
  "location_exclusions": ["excluded_place"],
  "other_party_preferences": {},
  "self_attributes": {},
  "primary_mutual_category": ["category"] (only if intent=mutual)
}
```

## FORMAT RULES (CRITICAL)

1. **Domains MUST be lowercase** with "&" symbol
   - ✅ "technology & electronics"
   - ❌ "Technology & Electronics"
   - ❌ "technology and electronics"

2. **Domain MUST be an array**, even for single value
   - ✅ domain: ["construction & trades"]
   - ❌ domain: "construction & trades"

3. **Intent/subintent MUST be lowercase**
   - ✅ "service", "provide"
   - ❌ "Service", "PROVIDE"

4. **Empty objects/arrays are valid**
   - ✅ "categorical": {}
   - ✅ "location_exclusions": []

5. **Numeric values in min/max/range need axis wrapper**
   - ✅ "min": {"cost": [{"type": "price", "value": 500, "unit": "INR"}]}
   - ❌ "min": {"price": 500}

6. **location_match_mode MUST always be present**
   - Default to "near_me" if no location mentioned
   - Use "explicit" if location is stated

## VALIDATION TASK

Given the JSON below, validate and correct:
1. Ensure domains are lowercase with "&"
2. Ensure domain is an array
3. Ensure intent/subintent are valid combinations
4. Ensure numeric constraints use proper axis structure
5. Return corrected JSON only, no explanation
