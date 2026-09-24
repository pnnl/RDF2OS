"""
Main workflow for the occupancy verification workflow.
"""

from typing import Dict, Optional
import logging
import pandas as pd
from data_processing import Config, DataLoader
from verification import Verifier, PassFailEvaluator, VerificationResult
from plotting import Visualizer, ExcelExporter

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_default_config() -> Config:
    """Return default configuration."""
    return Config()


class OccupancyVerificationWorkflow:
    """
    Main workflow for occupancy verification.
    """
    
    def __init__(self, config_name: str, config: Optional[Config] = None):
        self.config_name = config_name
        self.config = config or Config()
        
        self.loader = DataLoader(self.config)
        self.verifier = Verifier(self.config, self.config_name)
        self.evaluator = PassFailEvaluator(self.config)
        self.visualizer = Visualizer(self.config)
        self.exporter = ExcelExporter()
    
    def run_all(self) -> None:
        print(f"\n▶ Processing configuration: {self.config_name}")
        
        try:
            print("   Loading input data...")
            sim_data, config_data = self._load_data()
            
            self.config.ensure_output_dirs(self.config_name)
            output_dirs = self.config.get_output_dirs(self.config_name)
            
            print("   Computing percent differences...")
            diff_results = self._run_diff_verifications(sim_data, config_data)
            
            print("   Computing pass/fail results...")
            full_results = self._run_full_verifications(sim_data, config_data, diff_results)
            passfail_results = self._compute_passfail(full_results, config_data)
            
            print("   Running additional analysis...")
            self._run_additional_analysis(sim_data, config_data, output_dirs)
            
            print("   Generating plots and Excel reports...")
            self._generate_outputs(diff_results, passfail_results, output_dirs)
            
            print(f"✅ Successfully completed: {self.config_name}\n")
            
        except Exception as e:
            print(f"❌ Failed - An error occurred while processing {self.config_name}")
            print(f"   Details: {e}")
            logger.error("Workflow failed", exc_info=True)
            raise
    
    def _load_data(self):
        """Load both the simulation output files and the Excel configuration files."""
        sim_data = self.loader.load_simulation_data(self.config_name)
        config_data = self.loader.load_config_data(self.config_name)
        return sim_data, config_data
    
    def _run_diff_verifications(self, sim_data: Dict, config_data: Dict) -> Dict:
        """Run the percent difference verifications."""
        results = {}
        results['office'] = self.verifier.verify_office_breakdown(sim_data, config_data)
        results['behavior'] = self.verifier.verify_behavior(sim_data, config_data)
        results['meeting'] = self.verifier.verify_meeting(sim_data, config_data)
        return results
    
    def _run_full_verifications(self, sim_data: Dict, config_data: Dict, diff_results: Dict) -> Dict:
        """Run the full verifications used for pass/fail calculations."""
        full_results = {}
        full_results['office'] = diff_results['office']
        full_results['behavior'] = self.verifier.verify_behavior_full(sim_data, config_data)
        full_results['meeting'] = self.verifier.verify_meeting_full(sim_data, config_data)
        return full_results
    
    def _compute_passfail(self, full_results: Dict, config_data: Dict) -> Dict:
        """Compute pass/fail results for all verification types."""
        pf = {}
        pf['office'] = self.evaluator.evaluate_tolerance(full_results['office'])
        pf['behavior'] = self.evaluator.evaluate_behavior(
            full_results['behavior'], config_data, self.verifier.extractor
        )
        pf['meeting'] = self.evaluator.evaluate_meeting(full_results['meeting'])
        return pf
    
    def _run_additional_analysis(self, sim_data: Dict, config_data: Dict, output_dirs: Dict) -> None:
        """
        Runs the two deeper analyses:
        - Behavior Underuse Analysis: shows where time was redirected when
          simulated time in a space was below the configured target.
        - Meeting Length Bias Analysis: checks for bias toward longer or
          shorter meetings.
        """
        analysis_dir = output_dirs['percent_diff_data'].parent / 'analysis'
        analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # Behavior Underuse Analysis
        try:
            diff_df, underuse_summary = self.verifier.analyze_behavior_underuse(sim_data, config_data)
            output_file = analysis_dir / 'behavior_underuse_analysis.xlsx'
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                diff_df.to_excel(writer, sheet_name='Difference')
                underuse_summary.to_excel(writer, sheet_name='Underuse_Summary', index=False)
            print("   • Behavior underuse analysis exported")
        except Exception as e:
            logger.warning(f"Behavior underuse analysis failed: {e}")
        
        # Meeting Length Bias Analysis
        try:
            bias_df = self.verifier.analyze_meeting_length_bias(sim_data, config_data)
            if not bias_df.empty:
                output_file = analysis_dir / 'meeting_length_bias_analysis.xlsx'
                bias_df.to_excel(output_file, index=False)
                print("   • Meeting length bias analysis exported")
        except Exception as e:
            logger.warning(f"Meeting length bias analysis failed: {e}")
    
    def _generate_outputs(self, results: Dict, passfail_results: Dict, output_dirs: Dict) -> None:
        """Generate all plots and Excel files."""
        for name, result in results.items():
            if result.diff is not None and not result.diff.empty:
                plot_data = result.diff.T if name == 'behavior' else result.diff
                self.visualizer.generate_difference_heatmap(
                    plot_data,
                    output_dirs['percent_diff_plots'] / f'{name}_difference.png',
                    '% Difference Between Configured and Simulated Data'
                )
                self.exporter.export_diff(
                    result,
                    output_dirs['percent_diff_data'] / f'{name}_verification.xlsx'
                )
        
        for name, pf_df in passfail_results.items():
            if not pf_df.empty:
                self.visualizer.generate_passfail_heatmap(
                    pf_df,
                    output_dirs['pass_fail_plots'] / f'{name}_passfail.png',
                    'Pass/Fail Between Configured and Simulated Data'
                )
                result = results.get(name)
                if result:
                    self.exporter.export_passfail(
                        pf_df,
                        result,
                        output_dirs['pass_fail_data'] / f'{name}_passfail.xlsx'
                    )