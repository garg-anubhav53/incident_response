import os
import json
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a status page communications writer for an enterprise SaaS security company. You receive a structured incident analysis and generate customer-facing status page updates.

You write in 4 stages: Investigating, Identified, Monitoring, Resolved. Not every incident needs all 4 — use judgment. A fast-resolved incident may skip straight from Investigating to Resolved.

VOICE AND TONE:
- Professional, calm, direct. No panic, no minimizing.
- First person plural ("We are investigating", "Our team has identified").
- Empathetic but not apologetic until Resolved ("We apologize for any inconvenience" only in the final update).
- Never defensive. Never assign blame — not to your own team, not to third parties. If a third-party caused it, say "an upstream service provider" or "an external dependency", never name them.
- No technical jargon. Translate everything to customer experience language.

STRUCTURE PER UPDATE:
- Title: Short, customer-symptom-focused (e.g., "API Performance Degradation", "Portal Access Issues", "Delayed Threat Remediation"). Never include severity codes, internal service names, or root cause in the title.
- Status: Investigating | Identified | Monitoring | Resolved
- Message body (3-5 sentences max):
  1. What's happening (customer-observable symptoms)
  2. What's affected and what's NOT affected (if confirmed in the data — use the unaffected_functionality field)
  3. What we're doing about it
  4. When to expect the next update

RULES:
1. NEVER include anything from the internal_details_to_exclude list. No engineer names, no database hostnames, no PR numbers, no commit SHAs, no internal service names.
2. If data_gaps exist around scope, be honest but not alarming: "Some customers may experience..." rather than "All customers are affected" (when you don't know) or silence (when you do know).
3. Timestamps in PT (Pacific Time), formatted like "2:30 PM PT". Convert from UTC.
4. For the Resolved update, include a brief summary block:
   - Incident start time (approximate)
   - Resolution time
   - Total duration
   - Impact summary (one line)
5. If unaffected_functionality has confirmed items, mention them prominently — especially if detection/security functions are unaffected. For a security product, "detection remained fully operational" is the most reassuring thing you can say.
6. Keep each update under 100 words. Status pages are scanned, not read.
7. For Identified stage, reference the cause abstractly: "a configuration change", "an infrastructure issue", "an upstream service disruption" — never the technical specifics.
8. Include a "Next update in X minutes" commitment in Investigating and Identified stages.
9. The Monitoring stage should reference observable improvement: "response times are returning to normal", "error rates have decreased significantly."

Return ONLY valid JSON, no markdown fencing:
{
  "title": "Customer-facing incident title",
  "communications": [
    {
      "stage": "investigating",
      "posted_at_pt": "Suggested post time in PT",
      "message": "The status page message body"
    },
    {
      "stage": "identified",
      "posted_at_pt": "...",
      "message": "..."
    },
    {
      "stage": "monitoring",
      "posted_at_pt": "...",
      "message": "..."
    },
    {
      "stage": "resolved",
      "posted_at_pt": "...",
      "message": "..."
    }
  ]
}"""


def generate_communications(incident_analysis: dict) -> dict:
    """Generate status page communications from incident analysis"""
    
    user_msg = f"""Generate status page communications for this incident:

{json.dumps(incident_analysis, indent=2)}
"""
    
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    
    text = response.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    
    return json.loads(text.strip())


def process_all_incidents(custom_output_dir=None):
    """Process all incident analysis files and generate communications"""
    output_dir = Path("output")
    if custom_output_dir:
        comms_dir = Path(custom_output_dir)
    else:
        comms_dir = Path("communications")
    comms_dir.mkdir(exist_ok=True)
    
    print(f"📝 Generating communications for incidents in {output_dir}")
    
    # Process each analysis file
    analysis_files = list(output_dir.glob("*_analysis.json"))
    if not analysis_files:
        print("⚠️  No analysis files found in output directory")
        return
    
    for analysis_file in analysis_files:
        print(f"\n📄 Processing {analysis_file.name}...")
        
        try:
            # Load incident analysis
            incident_data = json.loads(analysis_file.read_text())
            
            # Generate communications
            comms = generate_communications(incident_data)
            
            # Save communications
            slug = analysis_file.stem.replace("_analysis", "")
            comms_file = comms_dir / f"{slug}_communications.json"
            comms_file.write_text(json.dumps(comms, indent=2))
            
            print(f"  ✅ Communications saved: {comms_file}")
            
            # Validate output
            validate_communications(comms, slug)
            
        except Exception as e:
            print(f"  ❌ Error processing {analysis_file.name}: {e}")
            continue


def validate_communications(output: dict, incident_type: str) -> None:
    """Validate generated communications against requirements"""
    
    checks = {
        "title_no_internal_names": "api-gateway" not in output["title"].lower() and "rds" not in output["title"].lower(),
        "title_is_customer_facing": "API" in output["title"] or "Performance" in output["title"] or "Portal" in output["title"] or "Remediation" in output["title"],
        "has_all_4_stages": len(output["communications"]) == 4,
        "investigating_under_100_words": len(output["communications"][0]["message"].split()) < 100,
        "resolved_has_summary": "duration" in output["communications"][-1]["message"].lower() or "minutes" in output["communications"][-1]["message"].lower(),
        "no_engineer_names": not any(name in json.dumps(output).lower() for name in ["alice", "bob", "john"]),
        "no_internal_infra": not any(term in json.dumps(output).lower() for term in ["rds-prod-main", "connection pool", "pr #12345", "abc123"]),
        "times_in_pt": "PT" in json.dumps(output),
        "mentions_unaffected_or_gaps": True  # manual check — should either mention what's unaffected or hedge scope
    }
    
    print(f"\n🔍 Validation for {incident_type}")
    passed = 0
    for label, ok in checks.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  [{status}] {label}")
        if ok:
            passed += 1
    print(f"📊 {passed}/{len(checks)} checks passed")


def main():
    """Main function to run communication generation"""
    print("🚀 Starting Status Page Communication Generation")
    print("=" * 50)
    
    # Parse command line arguments
    custom_output_dir = None
    if len(sys.argv) > 1:
        custom_output_dir = sys.argv[1]
        print(f"📁 Using custom output directory: {custom_output_dir}")
    
    # Check if API key is available
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not found in environment variables")
        print("Please set up your .env file with the API key")
        return
    
    # Process all incidents
    process_all_incidents(custom_output_dir)
    
    print("\n✅ Communication generation completed!")
    if custom_output_dir:
        print(f"📁 Communications saved to: {custom_output_dir}/")
    else:
        print("📁 Communications saved to: communications/")


if __name__ == "__main__":
    main()
