"""
Plotting and results files

Handles all visual output (heatmaps) and Excel export.
No calculation logic lives here - this file only takes finished
VerificationResult data and turns it into plots and spreadsheets.
"""

from pathlib import Path
import logging

import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend so plots save correctly in the background
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from data_processing import Config
from verification import VerificationResult

logger = logging.getLogger(__name__)


class Visualizer:
    """Creates difference and pass/fail heatmaps."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def generate_difference_heatmap(self, data: pd.DataFrame, output_path: Path,
                                     title: str, ylabel: str = 'Parameters') -> None:
        """Generate a red/blue % difference heatmap (blue = simulated lower, red = simulated higher)."""
        self._save_heatmap(
            data=data.astype(float),
            output_path=output_path,
            title=title,
            ylabel=ylabel,
            figure_size=self.config.heatmap_figure_size,
            font_size=self.config.heatmap_font_size,
            heatmap_kwargs=dict(
                cmap='bwr',
                vmin=self.config.heatmap_vmin,
                vmax=self.config.heatmap_vmax,
                annot=True,
                annot_kws={"size": self.config.heatmap_annot_size},
                cbar_kws={"label": "Difference (%)"},
            ),
        )
    
    def generate_passfail_heatmap(self, data: pd.DataFrame, output_path: Path,
                                   title: str, ylabel: str = 'Parameters') -> None:
        """Generate a red/green pass(1)/fail(0) heatmap."""
        self._save_heatmap(
            data=data.fillna(0).astype(int),
            output_path=output_path,
            title=title,
            ylabel=ylabel,
            figure_size=self.config.passfail_figure_size,
            font_size=self.config.passfail_font_size,
            heatmap_kwargs=dict(
                cmap='RdYlGn',
                vmin=0,
                vmax=1,
                cbar=False,
                annot=False,
            ),
        )
    
    def _save_heatmap(self, data: pd.DataFrame, output_path: Path, title: str, ylabel: str,
                       figure_size: tuple, font_size: int, heatmap_kwargs: dict) -> None:
        """
        Shared logic for building and saving a heatmap. Handles:
          - Deleting any existing file first (avoids stale plots on Windows)
          - Scaling figure width based on number of columns (avoids label overlap)
          - Rewriting column labels to be more descriptive and readable
        """
        output_path = Path(output_path)
        
        # Delete the old file first - this prevents Windows from showing a
        # stale/cached version of the plot if the file was previously open
        if output_path.exists():
            try:
                output_path.unlink()
            except PermissionError:
                logger.warning(f"Could not delete existing file (may be open elsewhere): {output_path}")
        
        plt.close('all')  # Close any leftover figures from a previous run
        plt.rcParams['font.size'] = font_size
        
        # Widen the figure automatically if there are many columns, so labels
        # don't get squeezed together and overlap (e.g. the 9-column meeting plot)
        base_width, base_height = figure_size
        num_cols = max(len(data.columns), 1)
        adjusted_width = max(base_width, num_cols * 1.9)
        
        fig, ax = plt.subplots(figsize=(adjusted_width, base_height))
        
        df_heat = data.copy()
        df_heat.index = df_heat.index.fillna('Unknown')
        df_heat.columns = df_heat.columns.fillna('Unknown')
        
        # Turn short technical column names into more descriptive labels,
        # then wrap them onto multiple lines (one phrase per line) so they
        # display cleanly under each column
        wrapped_columns = []
        for col in df_heat.columns:
            label = str(col).strip()
            label = label.replace('probability of', 'Probability of')
            label = label.replace('percent of time in', 'Percent of Time Spent in')
            label = label.replace('minimum number of', 'Minimum Number of')
            label = label.replace('maximum number of', 'Maximum Number of')
            label = label.replace('per day', 'Per Day')
            label = label.replace('per meeting', 'Per Meeting')
            wrapped_columns.append(label.replace(' ', '\n'))
        
        try:
            sns.heatmap(df_heat, ax=ax, lw=3, **heatmap_kwargs)
            ax.set_xticklabels(wrapped_columns, rotation=0, ha='center')
        except Exception as e:
            logger.error(f"Could not create heatmap: {e}")
            plt.close(fig)
            raise
        
        plt.title(title)
        plt.ylabel(ylabel)
        plt.xlabel('')
        plt.tight_layout()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        except PermissionError:
            logger.error(f"Permission denied saving to {output_path}. Close it if open elsewhere.")
            raise
        except Exception as e:
            logger.error(f"Failed to save plot: {e}")
            raise
        finally:
            # Always close the figure, even if saving failed, to free memory
            plt.close(fig)
            plt.close('all')


class ExcelExporter:
    """
    Writes VerificationResult (and optional pass/fail) data to Excel files.
    Each file contains three tabs with matching row/column order, so the
    Difference/PassFail, Simulated, and Configured values are easy to compare.
    """
    
    def export_diff(self, result: VerificationResult, output_path: Path) -> None:
        """Export percent difference results with three tabs: Difference, Simulated, Configured."""
        if result.diff is None or result.diff.empty:
            return
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        simulated = result.simulated.reindex(index=result.diff.index, columns=result.diff.columns)
        configured = result.configured.reindex(index=result.diff.index, columns=result.diff.columns)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            result.diff.to_excel(writer, sheet_name='Difference')
            simulated.to_excel(writer, sheet_name='Simulated')
            configured.to_excel(writer, sheet_name='Configured')
    
    def export_passfail(self, passfail: pd.DataFrame, result: VerificationResult,
                         output_path: Path) -> None:
        """Export pass/fail results with three tabs: PassFail, Simulated, Configured."""
        if passfail.empty:
            return
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        simulated = result.simulated.reindex(index=passfail.index, columns=passfail.columns)
        configured = result.configured.reindex(index=passfail.index, columns=passfail.columns)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            passfail.to_excel(writer, sheet_name='PassFail')
            simulated.to_excel(writer, sheet_name='Simulated')
            configured.to_excel(writer, sheet_name='Configured')