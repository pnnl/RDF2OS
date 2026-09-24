"""
Configuration and running script

INSTRUCTIONS:
1. Edit the CONFIG_NAMES list below
2. Run: python config.py
3. Check results in: ./verification_results/{CONFIG_NAME}/
"""

# ============================================================================
# *** EDIT THIS - Configuration names must match your input file name: "input_[insert your config name here]"" ***
# ============================================================================
CONFIG_NAMES = ['hflm_TYPI'] # Can run one or multiple configurations, i.e., ['hflm_TYPI', 'hflm_HAHM', 'hflm_HALM']
# ============================================================================

from workflow import OccupancyVerificationWorkflow, get_default_config
import logging

# Only show warnings and errors by default - keeps the terminal clean for users
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)




def main():
    """Run the verification workflow for every configuration in CONFIG_NAMES."""
    print("\n" + "="*70)
    print("OCCUPANCY VERIFICATION WORKFLOW")
    print("="*70)
    print(f"Running {len(CONFIG_NAMES)} configuration(s)...\n")
    
    successful = 0
    failed = []
    
    for config_name in CONFIG_NAMES:
        print(f"▶️Processing: {config_name}")
        
        try:
            workflow = OccupancyVerificationWorkflow(config_name)
            workflow.run_all()
            print(f"   ✅ Completed successfully\n")
            successful += 1
        except Exception as e:
            print(f"   ❌ Failed\n")
            failed.append((config_name, str(e)))
            logger.error(f"Failed on {config_name}", exc_info=True)
    
    # Print a final summary so the user can see the overall result at a glance
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"✅ Successful: {successful}/{len(CONFIG_NAMES)}")
    
    if failed:
        print(f"❌ Failed: {len(failed)}/{len(CONFIG_NAMES)}")
        for name, error in failed:
            print(f"   • {name}: {error}")
    
    print("\nResults are saved in:")
    for config_name in CONFIG_NAMES:
        print(f"   ./verification_results/{config_name}/")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()