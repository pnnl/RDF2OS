"""
Data Processing Layer

Loads simulation and configuration data.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import logging

import numpy as np
import pandas as pd
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Central configuration for the verification workflow."""
    
    # Folder locations - User must provide input and simulation result files
    input_data_path: Path = Path('./input_data')
    simulation_results_path: Path = Path('./input_data/simulation_results')
    config_files_path: Path = Path('./input_data/OOS_config_files')
    output_results_path: Path = Path('./verification_results')
    
    # Time settings used to convert simulation timesteps into hours/minutes and apply off-hours filtering
    # Off hours broken into morning and evening periods since calculations are based on 24 hour days
    timestep_per_hour: int = 12
    minutes_per_timestep: int = 5
    offhours_end: int = 72          # Timestep marking the end of off-hours at 6am: 6 hours X 12 timesteps/hour = 72
    evening_hours_start: int = 252   # Timestep marking start of evening off-hours at 9pm: 21 hours x 12 timesteps/hour = 252
    evening_hours_end: int = 288     # Timestep marking end of evening off-hours (12am): 24 hours x 12 timesteps/hour = 288
    
    # Pass/Fail tolerance: How close simulated values need to be to configured values to "pass"
    tolerance: float = 10.0
    
    # Plot appearance settings for % difference heatmaps
    heatmap_figure_size: Tuple[int, int] = (21, 11)
    heatmap_font_size: int = 25
    heatmap_annot_size: int = 25
    heatmap_vmin: float = -50.0
    heatmap_vmax: float = 50.0
    
    # Plot appearance settings for pass/fail heatmaps
    passfail_figure_size: Tuple[int, int] = (10, 8)
    passfail_font_size: int = 15
    
    # Internal caches so the code doesn't have to re-read input files mutltiple times for a single run
    _space_type_cache: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    _room_mapping_cache: Dict[str, pd.DataFrame] = field(default_factory=dict)
    
    def get_space_types(self, config_name: str) -> Dict[str, List[str]]:
        """Return office/gathering/other space types for this config."""
        if config_name not in self._space_type_cache:
            discoverer = SpaceTypeDiscovery(self)
            self._space_type_cache[config_name] = discoverer.get_space_types_from_excel(config_name)
        return self._space_type_cache[config_name]
    
    def get_room_spacetype_mapping(self, config_name: str) -> pd.DataFrame:
        """Return a table mapping each room to its space type"""
        if config_name not in self._room_mapping_cache:
            discoverer = SpaceTypeDiscovery(self)
            self._room_mapping_cache[config_name] = discoverer.get_rooms_and_spacetypes(config_name)
        return self._room_mapping_cache[config_name]
    
    def get_simulation_files(self, config_name: str) -> Dict[str, Path]:
        """Return file paths for the three required simulation output files."""
        config_dir = self.simulation_results_path / config_name
        return {
            'xml': config_dir / 'output_xml.xml',
            'by_room': config_dir / 'occSim.csv',
            'by_occupant': config_dir / 'occSim_by_Occupant.csv',
        }
    
    def get_config_file(self, config_name: str) -> Path:
        """Return the path to the Excel input file for this config."""
        return self.config_files_path / f'input_{config_name}.xlsx'
    
    def get_output_dirs(self, config_name: str) -> Dict[str, Path]:
        """Return all output folder paths where plots and Excel results will be saved."""
        config_out = self.output_results_path / config_name
        return {
            'percent_diff_plots': config_out / 'percent_difference' / 'plots',
            'percent_diff_data': config_out / 'percent_difference' / 'data',
            'pass_fail_plots': config_out / 'pass_fail' / 'plots',
            'pass_fail_data': config_out / 'pass_fail' / 'data',
        }
    
    def ensure_output_dirs(self, config_name: str) -> None:
        """Create all output folders if they don't already exist."""
        for dir_path in self.get_output_dirs(config_name).values():
            dir_path.mkdir(parents=True, exist_ok=True)


class SpaceTypeDiscovery:
    """Discovers space types from the Excel configuration files."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def get_space_types_from_excel(self, config_name: str) -> Dict[str, List[str]]:
        """
        Reads the space_type_input sheet and classifies each space type as
        'office' or 'gathering' based on which parameter rows are present:
        - Office spaces have rows like "occupant percentage" or "occupancy density"
        - Gathering/meeting spaces have rows like "minimum number of meeting per day"
            or "probability of X-min meetings"
        Any space type found in space_input but not listed in space_type_input
        is classified as 'other'.
        """
        config_file = self.config.get_config_file(config_name)
        
        space_type_input = pd.read_excel(config_file, sheet_name='space_type_input')
        space_input = pd.read_excel(config_file, sheet_name='space_input')
        
        all_columns = list(space_type_input.columns)
        num_space_types = len(all_columns) // 2  # Each space type takes up 2 columns
        
        # Keywords that only appear in office-style parameter rows
        office_keywords = ['occupant percentage', 'occupancy density']

        # Keywords that only appear in meeting/gathering-style parameter rows
        meeting_keywords = [
            'minimum number of meeting', 'maximum number of meeting',
            'minimum number of people', 'maximum number of people',
            'probability of'
        ]
        
        office_spaces = []
        gathering_spaces = []
        space_type_names = []
        
        for i in range(num_space_types):
            name_col_idx = i * 2
            space_name = all_columns[name_col_idx]
            space_type_names.append(space_name)
            
            # Look at every row label in this space type's column, not just the first row
            column_labels = space_type_input.iloc[:, name_col_idx].dropna().astype(str).str.lower()
            
            has_office_metric = any(
                any(kw in label for kw in office_keywords) for label in column_labels
            )
            has_meeting_metric = any(
                any(kw in label for kw in meeting_keywords) for label in column_labels
            )
            
            if has_office_metric and not has_meeting_metric:
                office_spaces.append(space_name)
            elif has_meeting_metric and not has_office_metric:
                gathering_spaces.append(space_name)
            elif has_office_metric and has_meeting_metric:
                logger.warning(
                    f"Space type '{space_name}' has both office-style and meeting-style "
                    f"parameters. Defaulting to 'gathering'. Please check the input file."
                )
                gathering_spaces.append(space_name)
            else:
                # Fall back to checking the first row's prefix, in case the metric
                # names don't match the expected keywords exactly
                first_row_label = space_type_input.iloc[0, name_col_idx]
                try:
                    prefix = str(first_row_label).split(':')[0].strip()
                except Exception:
                    prefix = ''
                
                if prefix.lower() == 'office':
                    office_spaces.append(space_name)
                else:
                    logger.warning(
                        f"Could not confidently classify space type '{space_name}' as "
                        f"office or gathering based on its parameters. Defaulting to "
                        f"'gathering'. Please check the input file."
                    )
                    gathering_spaces.append(space_name)
        
        other_spaces = []
        for space_type in space_input['Space Type'].dropna().unique():
            space_type_str = str(space_type).strip()
            if (space_type_str not in office_spaces and 
                space_type_str not in gathering_spaces and
                space_type_str not in space_type_names):
                other_spaces.append(space_type_str)
        
        return {
            'gathering': sorted(gathering_spaces),
            'office': sorted(office_spaces),
            'other': sorted(other_spaces),
            'all': space_type_names,
        }
    
    def get_rooms_and_spacetypes(self, config_name: str) -> pd.DataFrame:
        """Return a simple table of Room/Enclosure names paired with their Space Type."""
        config_file = self.config.get_config_file(config_name)
        space_input = pd.read_excel(config_file, sheet_name='space_input')
        return space_input[['Room/Enclosure', 'Space Type']].copy()


class DataLoader:
    """Loads simulation and configuration data from input files and simulation result files."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def load_csv(self, filepath: Path) -> pd.DataFrame:
        """Load a CSV file, trying a few different delimiters if the default fails."""
        if not filepath.exists():
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        try:
            return pd.read_csv(filepath, encoding='utf-8')
        except Exception:
            try:
                return pd.read_csv(filepath, sep=';', encoding='utf-8')
            except Exception:
                return pd.read_csv(filepath, sep='\t', encoding='utf-8')
    
    def load_excel(self, filepath: Path, sheet_name: str) -> pd.DataFrame:
        """Load a single sheet from an Excel file."""
        if not filepath.exists():
            raise FileNotFoundError(f"Excel file not found: {filepath}")
        return pd.read_excel(filepath, sheet_name=sheet_name)
    
    def load_xml(self, filepath: Path) -> ElementTree.Element:
        """Load the simulation output XML file."""
        if not filepath.exists():
            raise FileNotFoundError(f"XML file not found: {filepath}")
        return ElementTree.parse(filepath).getroot()
    
    def load_simulation_data(self, config_name: str) -> Dict:
        """
        Load all three simulation output files (room occupancy, occupant
        occupancy, and XML metadata) and clean up any extra empty columns.
        """
        files = self.config.get_simulation_files(config_name)
        
        by_room = self.load_csv(files['by_room'])
        # The occupant-level file has 6 header rows before the actual data starts
        by_occupant = pd.read_csv(files['by_occupant'], skiprows=6, encoding='utf-8')
        
        # Remove a trailing "Whole building" summary column if present
        if by_room.columns[-1] == 'Whole building':
            by_room = by_room.drop(columns=[by_room.columns[-1]])
        
        # Remove a trailing blank column if present
        if by_occupant.columns[-1] == '' or pd.isna(by_occupant.columns[-1]):
            by_occupant = by_occupant.iloc[:, :-1]
        
        xml_root = self.load_xml(files['xml'])
        
        return {
            'by_room': by_room,
            'by_occupant': by_occupant,
            'xml_root': xml_root
        }
    
    def load_config_data(self, config_name: str) -> Dict:
        """Load all three sheets from the Excel configuration file."""
        filepath = self.config.get_config_file(config_name)
        return {
            'space_input': self.load_excel(filepath, 'space_input'),
            'space_type_input': self.load_excel(filepath, 'space_type_input'),
            'behavior_input': self.load_excel(filepath, 'behavior_input'),
        }


class DataProcessor:
    """Reshapes and filters raw occupancy time-series data."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def reshape_to_2d_days(self, yearlist: List[float]) -> np.ndarray:
        """
        Convert a flat, year-long list of timestep values into a 2D array
        where each column is one day and each row is one timestep of that day.
        """
        timesteps_per_day = 24 * self.config.timestep_per_hour
        num_days = len(yearlist) // timesteps_per_day
        return np.reshape(yearlist, [timesteps_per_day, num_days], order='F')
    
    def apply_offhours_filter(self, arr: np.ndarray, val: float = 0) -> np.ndarray:
        """
        Zero out (or set to `val`) any timesteps that fall outside normal
        working hours, so off-hours activity doesn't affect the results.
        """
        arr = arr.copy()  # Copy first so we don't modify the caller's original array
        arr[0:self.config.offhours_end, :] = val
        arr[self.config.evening_hours_start:self.config.evening_hours_end, :] = val
        return arr
    
    def get_individual_days_by_dayofweek(self, yearlist: List[float]) -> Dict[str, np.ndarray]:
        """
        Split a year-long occupancy list into 7 groups, one per day of the
        week, each containing every occurrence of that day across the year.
        """
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        days_2d = self.reshape_to_2d_days(yearlist)
        result = {}
        for d_idx, day_name in enumerate(days):
            # Every 7th column belongs to the same day of the week
            day_data = self.apply_offhours_filter(days_2d[:, d_idx::7])
            result[day_name] = day_data
        return result
    
    def get_days_with_occupancy(self, yearlist: List[float]) -> List[str]:
        """Return the names of days of the week that show any occupancy at all."""
        days_dict = self.get_individual_days_by_dayofweek(yearlist)
        return [day for day, data in days_dict.items() if np.sum(data) > 0]


class OccupantInfoExtractor:
    """Extracts occupant assignments from XML and configured values from Excel."""
    
    def get_occupant_info(self, xml_root: ElementTree.Element) -> pd.DataFrame:
        """
        Read each occupant's assigned office and job type from the
        simulation XML file.
        """
        occupant_ids, offices, job_types = [], [], []
        
        occupants_elem = xml_root.find('Occupants')
        if occupants_elem is None:
            raise ValueError("Could not find Occupants element in XML")
        
        for occ in occupants_elem:
            occ_id = occ.get('ID')
            occupant_ids.append(occ_id)
            # The office ID is everything in the occupant ID except the last segment
            offices.append('_'.join(occ_id.split('_')[0:-1]))
            
            job_type_elem = occ.find('JobType')
            job_types.append(job_type_elem.text if job_type_elem is not None else 'Unknown')
        
        return pd.DataFrame({
            'Occupant': list(range(len(occupant_ids))),
            'Office': offices,
            'Job Type': job_types
        })
    
    def get_configured_occupant_types(self, config_data: Dict) -> pd.DataFrame:
        """
        Read the configured occupant type percentages for each space type
        from the space_type_input sheet.
        """
        space_type_input = config_data['space_type_input']
        all_columns = list(space_type_input.columns)
        # Space type names are in every other column (name, value, name, value, ...)
        space_types = [all_columns[i] for i in range(0, len(all_columns), 2)]
        
        all_labels = space_type_input.iloc[1:, 0].tolist()
        cleaned_labels = []
        for label in all_labels:
            try:
                cleaned_labels.append(label.split('-')[-1].split('[')[0].strip())
            except Exception:
                cleaned_labels.append(str(label))
        
        result_df = pd.DataFrame()
        for space_type in space_types:
            col_idx = all_columns.index(space_type)
            result_df[space_type] = space_type_input.iloc[1:, col_idx + 1].tolist()
        
        result_df.insert(0, 'labels', cleaned_labels)
        result_df.set_index('labels', inplace=True)
        result_df = result_df.dropna(how='all')
        result_df = result_df.sort_index(axis=0, ascending=True)
        
        return result_df
    
    def get_configured_behavior(self, config_data: Dict) -> pd.DataFrame:
        """
        Read only the configured space usage percentages (Own Office, Other
        Office, Meeting Rooms, Auxiliary, Outdoor) from the behavior_input sheet.
        Rows for average stay duration are excluded since those aren't
        percentages.
        """
        behavior_input = config_data['behavior_input']
        all_columns = list(behavior_input.columns)
        occ_types = [all_columns[i] for i in range(0, len(all_columns), 2)]
        all_labels = behavior_input.iloc[1:, 0].tolist()
        
        space_keywords = ['own office', 'other office', 'meeting room', 'auxiliary', 'outdoor']
        
        selected_indices, selected_labels = [], []
        for idx, label in enumerate(all_labels):
            if pd.isna(label):
                continue
            label_str = str(label).lower()
            # Only keep rows that are percentages, not stay-duration rows
            if 'percent' in label_str and any(kw in label_str for kw in space_keywords):
                if 'stay' not in label_str and 'average' not in label_str:
                    selected_indices.append(idx + 1)  # +1 because row 0 is the header
                    selected_labels.append(label)
        
        if not selected_indices:
            return pd.DataFrame()
        
        result_df = pd.DataFrame()
        for occ_type in occ_types:
            col_idx = all_columns.index(occ_type)
            values = [behavior_input.iloc[i, col_idx + 1] for i in selected_indices]
            result_df[occ_type] = values
        
        # Clean up labels for display (remove units in brackets, prefixes, etc.)
        cleaned_labels = []
        for label in selected_labels:
            try:
                cleaned_labels.append(str(label).split('[')[0].split(':')[-1].split('-')[-1].strip())
            except Exception:
                cleaned_labels.append(str(label))
        
        result_df.insert(0, 'labels', cleaned_labels)
        result_df.set_index('labels', inplace=True)
        
        for col in result_df.columns:
            result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
        
        return result_df
    
    def get_configured_behavior_full(self, config_data: Dict) -> pd.DataFrame:
        """
        Read ALL configured behavior parameters needed for pass/fail checks:
        Days of week, Arrival Time, Departure Time, and Space Percentages.
        This is a superset of get_configured_behavior().
        """
        behavior_input = config_data['behavior_input']
        all_columns = list(behavior_input.columns)
        occ_types = [all_columns[i] for i in range(0, len(all_columns), 2)]
        all_labels = behavior_input.iloc[1:, 0].tolist()
        
        # Each rule includes rows containing this keyword, unless they
        # also contain one of the exclude keywords (used to skip stay-duration rows)
        include_rules = [
            ('day', ['stay', 'average']),
            ('arrival time', ['variation', 'stay']),
            ('departure time', ['variation', 'stay']),
            ('own office', ['stay', 'average']),
            ('other office', ['stay', 'average']),
            ('meeting room', ['stay', 'average']),
            ('auxiliary', ['stay', 'average']),
            ('outdoor', ['stay', 'average']),
        ]
        
        selected_indices, selected_labels = [], []
        for idx, label in enumerate(all_labels):
            if pd.isna(label):
                continue
            label_str = str(label).lower()
            for include_kw, exclude_kws in include_rules:
                if include_kw in label_str and not any(ex in label_str for ex in exclude_kws):
                    selected_indices.append(idx + 1)
                    selected_labels.append(label)
                    break
        
        if not selected_indices:
            return pd.DataFrame()
        
        result_df = pd.DataFrame()
        for occ_type in occ_types:
            col_idx = all_columns.index(occ_type)
            values = [behavior_input.iloc[i, col_idx + 1] for i in selected_indices]
            result_df[occ_type] = values
        
        # Build display-friendly labels. Space-percentage rows keep the
        # "percent of time in X" phrasing; everything else just keeps the
        # short parameter name (Days, typical arrival time, typical departure time).
        cleaned_labels = []
        for label in selected_labels:
            label_str = str(label)
            label_lower = label_str.lower()
            
            if 'percent of time in space' in label_lower:
                # Extract just the space name after the dash, e.g. "Own office"
                try:
                    space_name = label_str.split('[')[0].split('-')[-1].strip()
                except Exception:
                    space_name = label_str
                cleaned_labels.append(f"percent of time in {space_name}")
            else:
                # For Days / Arrival / Departure, strip the occupant prefix and units
                try:
                    cleaned_labels.append(label_str.split('[')[0].split(':')[-1].strip())
                except Exception:
                    cleaned_labels.append(label_str)
        
        result_df.insert(0, 'labels', cleaned_labels)
        result_df.set_index('labels', inplace=True)
        
        return result_df
    
    def get_arrival_departure_variation(self, config_data: Dict) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Read the configured arrival/departure time variation windows (in
        minutes) for each occupant type. These define how much tolerance
        is allowed when checking simulated arrival/departure times.
        """
        behavior_input = config_data['behavior_input']
        all_columns = list(behavior_input.columns)
        occ_types = [all_columns[i] for i in range(0, len(all_columns), 2)]
        all_labels = behavior_input.iloc[1:, 0].tolist()
        
        arrival_variation, departure_variation = {}, {}
        
        for idx, label in enumerate(all_labels):
            if pd.isna(label):
                continue
            label_str = str(label).lower()
            
            if 'arrival' in label_str and 'variation' in label_str:
                for occ_type in occ_types:
                    col_idx = all_columns.index(occ_type)
                    try:
                        arrival_variation[occ_type] = float(behavior_input.iloc[idx + 1, col_idx + 1])
                    except Exception:
                        arrival_variation[occ_type] = 0.0
            
            elif 'departure' in label_str and 'variation' in label_str:
                for occ_type in occ_types:
                    col_idx = all_columns.index(occ_type)
                    try:
                        departure_variation[occ_type] = float(behavior_input.iloc[idx + 1, col_idx + 1])
                    except Exception:
                        departure_variation[occ_type] = 0.0
        
        return arrival_variation, departure_variation