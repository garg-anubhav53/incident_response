import json

# Load pipeline v2 output
with open("output/data_analysis.json", "r") as f:
    v2_result = json.load(f)

# Pipeline v1 expected validation checks
def validate_v1_expectations(result: dict) -> None:
    checks = [
        ("affected_service == api-gateway",
         result.get("affected_service", "").lower() == "api-gateway"),
        ("severity == SEV-2",
         result.get("severity", "").upper() == "SEV-2"),
        ("root_cause mentions timeout or PR #12345",
         any(kw in json.dumps(result.get("root_cause", {})).lower()
             for kw in ["timeout", "pr #12345", "pr#12345"])),
        ("trigger_time is around 14:15-14:20 UTC",
         any(ts in result.get("timeline", {}).get("cause_time_utc", "")
             for ts in ["14:15", "14:20", "22:15", "22:20"])),
        ("resolution mentions rollback",
         any(kw in json.dumps(result.get("resolution", {})).lower()
             for kw in ["rollback", "rolled back"])),
        ("customer_impact severity == degraded_performance",
         result.get("customer_impact", {}).get("severity_assessment") == "degraded_performance"),
        ("data_gaps mentions customers or regional scope",
         any(kw in " ".join(result.get("data_gaps", [])).lower()
             for kw in ["regional", "customer", "region", "which product"])),
        ("internal_details includes rds-prod-main",
         any("rds-prod-main" in d for d in result.get("internal_details_to_exclude", []))),
        ("internal_details includes engineer names",
         any(name in " ".join(result.get("internal_details_to_exclude", []))
             for name in ["alice", "bob", "john"])),
    ]
    
    print("🔍 Pipeline V1 Expectations vs V2 Output Analysis")
    print("=" * 60)
    
    passed = 0
    for label, ok in checks:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  [{status}] {label}")
        if ok:
            passed += 1
        else:
            # Show details for failed checks
            if "affected_service" in label:
                actual = result.get("affected_service", "")
                print(f"           Expected: api-gateway, Got: {actual}")
            elif "severity" in label:
                actual = result.get("severity", "")
                print(f"           Expected: SEV-2, Got: {actual}")
            elif "trigger_time" in label:
                actual = result.get("timeline", {}).get("trigger_time_utc", "")
                print(f"           Expected: 14:15-14:20 UTC, Got: {actual}")
    
    print(f"\n📊 {passed}/{len(checks)} V1 expectations met by V2 output")
    
    # Show detailed comparison for key fields
    print("\n📋 Detailed Field Comparison:")
    print("-" * 40)
    
    print(f"Affected Service: {result.get('affected_service', 'N/A')}")
    print(f"Severity: {result.get('severity', 'N/A')}")
    print(f"Customer Impact Severity: {result.get('customer_impact', {}).get('severity_assessment', 'N/A')}")
    print(f"Trigger Time: {result.get('timeline', {}).get('cause_time_utc', 'N/A')}")
    
    root_cause_text = json.dumps(result.get('root_cause', {}), indent=2)
    source_attribution_text = json.dumps(result.get('source_attribution', {}), indent=2)
    combined_text = root_cause_text + " " + source_attribution_text
    
    has_timeout = "timeout" in combined_text.lower()
    has_pr = "pr #12345" in combined_text.lower() or "pr#12345" in combined_text.lower()
    print(f"Root Cause mentions timeout: {has_timeout}")
    print(f"Root Cause mentions PR #12345: {has_pr}")
    
    resolution_text = json.dumps(result.get('resolution', {}), indent=2)
    has_rollback = "rollback" in resolution_text.lower() or "rolled back" in resolution_text.lower()
    print(f"Resolution mentions rollback: {has_rollback}")
    
    data_gaps = result.get('data_gaps', [])
    has_customer_scope = any(kw in " ".join(data_gaps).lower() for kw in ["regional", "customer", "region", "which product"])
    print(f"Data gaps mention customer/regional scope: {has_customer_scope}")
    
    internal_details = result.get('internal_details_to_exclude', [])
    has_rds = any("rds-prod-main" in d for d in internal_details)
    has_engineers = any(name in " ".join(internal_details) for name in ["alice", "bob", "john"])
    print(f"Internal details include rds-prod-main: {has_rds}")
    print(f"Internal details include engineer names: {has_engineers}")

if __name__ == "__main__":
    validate_v1_expectations(v2_result)
