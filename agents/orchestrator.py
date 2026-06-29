import argparse

# Pillar 1
from agents.sponsor.outreach_agent import batch_outreach
from agents.sponsor.response_tracker import check_responses

# Pillar 2
from agents.social_media.scheduler import schedule_weekly_content, check_github_for_milestone

# Pillar 3
from agents.analysis.code_improvement_agent import analyze_autonomous_code

def run_sponsor_cycle(mock: bool = True):
    print("--- Starting Sponsor Cycle ---")
    batch_outreach("data/sponsors/target_companies.csv", mock=mock)
    check_responses(mock=mock)
    print("--- Completed Sponsor Cycle ---")

def run_social_cycle(mock: bool = True):
    print("--- Starting Social Media Cycle ---")
    schedule_weekly_content(mock=mock)
    check_github_for_milestone(mock=mock)
    print("--- Completed Social Media Cycle ---")

def run_code_cycle(mock: bool = True):
    print("--- Starting Code Analysis Cycle ---")
    analyze_autonomous_code(mock=mock)
    print("--- Completed Code Analysis Cycle ---")

def main():
    parser = argparse.ArgumentParser(description="AGÜ FCEV Multi-Agent Orchestrator")
    parser.add_argument("--cycle", type=str, choices=["sponsor", "social", "code", "all"], default="all",
                        help="Which agent cycle to run")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (no real API calls)", default=True)
    
    args = parser.parse_args()
    
    if args.cycle in ["sponsor", "all"]:
        run_sponsor_cycle(mock=args.mock)
        
    if args.cycle in ["social", "all"]:
        run_social_cycle(mock=args.mock)
        
    if args.cycle in ["code", "all"]:
        run_code_cycle(mock=args.mock)

if __name__ == "__main__":
    main()
