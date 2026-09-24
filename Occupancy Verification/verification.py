"""
Verification Calculations

Contains all logic for comparing simulated results against configured values.
Each verification method returns a VerificationResult object containing
configured values, simulated values, and (when applicable) their difference.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import logging

import numpy as np
import pandas as pd

from data_processing import Config, DataProcessor, OccupantInfoExtractor

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Container for configured values, simulated values, and their difference."""
    configured: pd.DataFrame
    simulated: pd.DataFrame
    diff: Optional[pd.DataFrame] = None


class Verifier:
    """Performs all verification calculations (office, behavior, and meeting)."""
    
    def __init__(self, config: Config, config_name: str):
        self.config = config
        self.config_name = config_name
        self.processor = DataProcessor(config)
        self.extractor = OccupantInfoExtractor()
    
    def verify_office_breakdown(self, sim_data: Dict, config_data: Dict) -> VerificationResult:
        """Compares configured occupant type percentages with simulated percentages
        for each space that has occupants assigned to it."""
        occ_info = self.extractor.get_occupant_info(sim_data['xml_root'])
        configured = self.extractor.get_configured_occupant_types(config_data)
        
        configured = configured[configured.index.notna()]
        configured = configured[configured.index != 'nan']
        configured = configured[configured.index != 'Unknown']
        
        for col in configured.columns:
            configured[col] = pd.to_numeric(configured[col], errors='coerce')
        configured = configured.dropna(how='all')
        
        room_mapping = self.config.get_room_spacetype_mapping(self.config_name)
        room_to_spacetype = dict(zip(
            room_mapping['Room/Enclosure'].astype(str),
            room_mapping['Space Type']
        ))
        
        occupied_space_types = {
            room_to_spacetype.get(str(office_id), 'Unknown')
            for office_id in occ_info['Office']
        } - {'Unknown'}
        
        office_columns = [c for c in configured.columns if c in occupied_space_types]
        if not office_columns:
            logger.warning(f"No occupied space types found for {self.config_name}")
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        configured = configured[office_columns]
        
        occ_type_df = pd.DataFrame({
            'Office': [room_to_spacetype.get(str(o), 'Unknown') for o in occ_info['Office']],
            'Occupant Type': occ_info['Job Type']
        })
        
        simulated = pd.DataFrame(index=configured.index)
        for office_type in configured.columns:
            office_occs = occ_type_df.loc[occ_type_df['Office'] == office_type, 'Occupant Type']
            if len(office_occs) > 0:
                simulated[office_type] = [
                    (office_occs == occtype).sum() / len(office_occs) * 100
                    for occtype in configured.index
                ]
            else:
                simulated[office_type] = [0.0] * len(configured.index)
        
        configured = configured.fillna(0).astype(float)
        simulated = simulated[configured.columns].fillna(0).astype(float)
        diff = simulated - configured
        
        return VerificationResult(configured, simulated, diff)
    
    def verify_behavior(self, sim_data: Dict, config_data: Dict) -> VerificationResult:
        """Compares configured versus simulated space usage percentages only."""
        configured = self.extractor.get_configured_behavior(config_data)
        if configured.empty:
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        simulated_space_dist = self._calculate_space_distribution(sim_data, config_data)
        simulated = self._align_to_space_labels(configured, simulated_space_dist)
        
        configured_num = configured.apply(pd.to_numeric, errors='coerce').fillna(0)
        simulated_num = simulated.apply(pd.to_numeric, errors='coerce').fillna(0)
        diff = simulated_num - configured_num
        
        return VerificationResult(configured_num.T, simulated_num.T, diff.T)
    
    def verify_behavior_full(self, sim_data: Dict, config_data: Dict) -> VerificationResult:
        """Compares all behavior parameters needed for pass/fail evaluation."""
        occ_info = self.extractor.get_occupant_info(sim_data['xml_root'])
        by_occupant = sim_data['by_occupant']
        configured = self.extractor.get_configured_behavior_full(config_data)
        
        if configured.empty:
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        simulated_space_dist = self._calculate_space_distribution(sim_data, config_data)
        job_types = sorted(set(occ_info['Job Type']))
        
        arrival_times, departure_times, days_present = {}, {}, {}
        
        for job_type in job_types:
            occ_indices = occ_info.loc[occ_info['Job Type'] == job_type, 'Occupant'].tolist()
            arrivals, departures, all_days = [], [], []
            
            for occ_idx in occ_indices:
                if str(occ_idx) not in by_occupant.columns:
                    continue
                try:
                    yearlist = by_occupant[str(occ_idx)].tolist()
                    days_2d = self.processor.reshape_to_2d_days(yearlist)
                    days_2d_filtered = self.processor.apply_offhours_filter(days_2d, val=-1)
                    
                    presence = days_2d_filtered >= 0
                    change = np.diff(presence, n=1, axis=0, prepend=0).astype(int)
                    
                    for day_idx in range(days_2d_filtered.shape[1]):
                        arr = np.where(change[:, day_idx] == 1)[0]
                        dep = np.where(change[:, day_idx] == -1)[0]
                        if len(arr):
                            arrivals.append(int(np.min(arr)))
                        if len(dep):
                            departures.append(int(np.max(dep)))
                    
                    all_days.extend(self.processor.get_days_with_occupancy(yearlist))
                except Exception:
                    pass
            
            if arrivals:
                arrival_times[job_type] = int(np.round(np.median(arrivals)))
            if departures:
                departure_times[job_type] = int(np.round(np.median(departures)))
            if all_days:
                days_present[job_type] = ', '.join(sorted(set(all_days)))
        
        space_mapping = {
            'Own office': 'Own Office',
            'Other office': 'Office',
            'Meeting room': 'Gathering',
            'Auxiliary': 'Other',
            'Outdoor': 'Outdoor'
        }
        
        simulated = pd.DataFrame(index=configured.index, columns=configured.columns)
        
        for job_type in configured.columns:
            for param_label in configured.index:
                param_lower = param_label.lower()
                
                if 'day' in param_lower:
                    simulated.at[param_label, job_type] = days_present.get(job_type, '')
                elif 'arrival' in param_lower:
                    ts = arrival_times.get(job_type, 0)
                    simulated.at[param_label, job_type] = self._timestep_to_str(ts)
                elif 'departure' in param_lower:
                    ts = departure_times.get(job_type, 0)
                    simulated.at[param_label, job_type] = self._timestep_to_str(ts)
                else:
                    matched = next((v for k, v in space_mapping.items() if k in param_lower), None)
                    if matched and matched in simulated_space_dist.index and job_type in simulated_space_dist.columns:
                        simulated.at[param_label, job_type] = simulated_space_dist.at[matched, job_type]
                    else:
                        simulated.at[param_label, job_type] = 0.0
        
        return VerificationResult(configured.T, simulated.T, diff=None)

    def _timestep_to_str(self, timestep: int) -> str:
        """Convert a timestep index into an HH:MM string."""
        hours = timestep // self.config.timestep_per_hour
        minutes = (timestep % self.config.timestep_per_hour) * self.config.minutes_per_timestep
        return f"{hours:02d}:{minutes:02d}"
    
    def _align_to_space_labels(self, configured: pd.DataFrame, simulated_space_dist: pd.DataFrame) -> pd.DataFrame:
        """Map configured row labels to the corresponding simulated space categories."""
        space_mapping = {
            'Own office': 'Own Office',
            'Other office': 'Office',
            'Meeting room': 'Gathering',
            'Auxiliary': 'Other',
            'Outdoor': 'Outdoor'
        }
        
        simulated = pd.DataFrame(index=configured.index, columns=configured.columns)
        for cfg_label in configured.index:
            matched = next((v for k, v in space_mapping.items() if k in cfg_label.lower()), None)
            if matched and matched in simulated_space_dist.index:
                for job_type in configured.columns:
                    if job_type in simulated_space_dist.columns:
                        simulated.at[cfg_label, job_type] = simulated_space_dist.at[matched, job_type]
                    else:
                        simulated.at[cfg_label, job_type] = 0.0
            else:
                simulated.loc[cfg_label] = 0.0
        return simulated
    
    def _calculate_space_distribution(self, sim_data: Dict, config_data: Dict) -> pd.DataFrame:
        """Calculate what percentage of time each occupant type spends in each space category."""
        by_occupant = sim_data['by_occupant']
        occ_info = self.extractor.get_occupant_info(sim_data['xml_root'])
        
        occsim_byocc_file = self.config.get_simulation_files(self.config_name)['by_occupant']
        room_number_row = pd.read_csv(occsim_byocc_file, skiprows=lambda x: x not in [2], nrows=1)
        room_id_row = pd.read_csv(occsim_byocc_file, skiprows=lambda x: x not in [3], nrows=1)
        
        room_numbers = list(room_number_row.columns[:-1])
        room_ids = list(room_id_row.columns[:-1])
        
        simroom_map = pd.DataFrame({
            'roomnumber': room_numbers[1:],
            'roomid': room_ids[1:],
        })
        
        room_mapping = self.config.get_room_spacetype_mapping(self.config_name)
        room_to_spacetype = dict(zip(
            room_mapping['Room/Enclosure'].astype(str),
            room_mapping['Space Type']
        ))
        space_types = self.config.get_space_types(self.config_name)
        
        def classify(room_id: str) -> str:
            st = room_to_spacetype.get(str(room_id), 'Unknown')
            if st in space_types['office']:
                return 'Office'
            elif st in space_types['gathering']:
                return 'Gathering'
            return 'Other'
        
        roomnames = []
        for idx, row in simroom_map.iterrows():
            if idx == 0:
                roomnames.append('Outdoor')
            elif idx == len(simroom_map) - 1:
                roomnames.append('Away')
            else:
                roomnames.append(classify(row['roomid']))
        simroom_map['roomname'] = roomnames
        
        own_office = {}
        for occ in occ_info['Occupant']:
            office_sp = occ_info.loc[occ_info['Occupant'] == occ, 'Office'].values[0]
            matches = simroom_map.loc[simroom_map['roomid'] == str(office_sp), 'roomnumber']
            if len(matches) > 0:
                own_office[occ] = matches.values[0]
        
        data = by_occupant.iloc[:, 2:]
        num_rooms = int(np.max(np.max(data)))
        
        rooms_occs = np.zeros((num_rooms + 1, np.shape(data)[1]))
        for i in range(0, num_rooms + 1):
            rooms_occs[i, :] = np.sum(data == i, axis=0)
        
        oo_perc = np.zeros((1, np.shape(data)[1]))
        for occ in own_office.keys():
            try:
                room = int(own_office[occ])
                oo_perc[0, occ] = rooms_occs[room, occ]
                rooms_occs[room, occ] = 0
            except Exception:
                pass
        
        rooms_occs = np.append(rooms_occs, oo_perc, axis=0)
        rooms_occs_df = pd.DataFrame(rooms_occs)
        rooms_occs_df.columns = data.columns
        
        ST = {st: [] for st in set(simroom_map['roomname'].iloc[0:-1])}
        for i in range(len(simroom_map['roomname'].iloc[0:-1])):
            ST[simroom_map['roomname'].iloc[i]].append(simroom_map['roomnumber'].iloc[i])
        ST['Own Office'] = [num_rooms + 1]
        
        OT = {ot: [] for ot in set(occ_info['Job Type'])}
        for i in range(len(occ_info['Occupant'])):
            OT[occ_info['Job Type'].iloc[i]].append(occ_info['Occupant'].iloc[i])
        
        DF_OT = pd.DataFrame()
        for ot in OT.keys():
            temp = []
            for st in ST.keys():
                vals = [int(s) for s in ST[st]]
                valid_vals = [v for v in vals if v < rooms_occs_df.shape[0]]
                arr = rooms_occs_df.iloc[valid_vals, OT[ot]]
                temp.append(np.sum(np.sum(arr)))
            DF_OT[ot] = temp
        
        DF_OT['space types'] = list(ST.keys())
        DF_OT.set_index('space types', inplace=True)
        DF_OT = np.round(DF_OT / np.sum(DF_OT, axis=0) * 100)
        DF_OT = DF_OT[sorted(DF_OT.columns)]
        
        return DF_OT
    
    def analyze_behavior_underuse(self, sim_data: Dict, config_data: Dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        When simulated time in a space is below the configured target,
        this analysis shows where the extra time was spent instead.
        """
        configured = self.extractor.get_configured_behavior(config_data)
        if configured.empty:
            return pd.DataFrame(), pd.DataFrame()
        
        simulated_space_dist = self._calculate_space_distribution(sim_data, config_data)
        simulated = self._align_to_space_labels(configured, simulated_space_dist)
        
        configured = configured.apply(pd.to_numeric, errors='coerce').fillna(0)
        simulated = simulated.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        diff_df = simulated - configured
        
        summary_rows = []
        for ot in diff_df.columns:
            for space in diff_df.index:
                delta = diff_df.at[space, ot]
                if delta < -0.1:
                    # List every other space, sorted by largest positive delta first,
                    # so we can see where time was redirected even if the gain is small
                    other_deltas = [
                        (other_space, diff_df.at[other_space, ot])
                        for other_space in diff_df.index
                        if other_space != space
                    ]
                    other_deltas.sort(key=lambda x: x[1], reverse=True)
                    
                    where_time_went = [
                        f"{other_space} ({'+' if d >= 0 else ''}{d:.1f}%)"
                        for other_space, d in other_deltas
                        if abs(d) > 0.05
                    ]
                    
                    summary_rows.append({
                        'OccupantType': ot,
                        'UnderusedSpace': space,
                        'ConfiguredPct': configured.at[space, ot],
                        'SimulatedPct': simulated.at[space, ot],
                        'DeltaPct': round(delta, 1),
                        'WhereTimeWent': "; ".join(where_time_went) if where_time_went else "No significant gains elsewhere"
                    })
        
        underuse_summary = pd.DataFrame(summary_rows)
        return diff_df, underuse_summary
    
    def analyze_meeting_length_bias(self, sim_data: Dict, config_data: Dict) -> pd.DataFrame:
        """
        Analyzes whether the simulation favors longer (120-min) or shorter
        (60-min) meetings compared to the configured probabilities.
        """
        try:
            from scipy import ndimage
        except ImportError:
            logger.warning("scipy not installed, skipping meeting bias analysis")
            return pd.DataFrame()
        
        by_room = sim_data['by_room']
        meeting_rooms = self._get_meeting_rooms(sim_data, config_data)
        configured = self._extract_meeting_config_full(config_data, meeting_rooms)
        
        bias_data = []
        
        for room_id in meeting_rooms:
            if room_id not in by_room.columns:
                continue
                
            try:
                room_2d = self.processor.reshape_to_2d_days(by_room[room_id].tolist())
                room_2d = self.processor.apply_offhours_filter(room_2d)
                
                lengths = []
                for day_idx in range(room_2d.shape[1]):
                    occupied = room_2d[:, day_idx] > 0
                    labeled, num_features = ndimage.label(occupied)
                    for meeting_id in range(1, num_features + 1):
                        mask = labeled == meeting_id
                        lengths.append(np.sum(mask) * self.config.minutes_per_timestep)
                
                total = len(lengths)
                if total == 0:
                    continue
                    
                sim_60 = sum(1 for l in lengths if l == 60) / total * 100
                sim_120 = sum(1 for l in lengths if l == 120) / total * 100
                
                if room_id in configured.columns:
                    cfg_60 = configured.at['probability of 60-min meetings', room_id] \
                        if 'probability of 60-min meetings' in configured.index else 0
                    cfg_120 = configured.at['probability of 120-min meetings', room_id] \
                        if 'probability of 120-min meetings' in configured.index else 0
                else:
                    cfg_60, cfg_120 = 0, 0
                
                cfg_60 = float(cfg_60) if pd.notna(cfg_60) else 0.0
                cfg_120 = float(cfg_120) if pd.notna(cfg_120) else 0.0
                
                bias_data.append({
                    'Room': room_id,
                    'Configured_60': cfg_60,
                    'Simulated_60': round(sim_60, 1),
                    'Delta_60': round(sim_60 - cfg_60, 1),
                    'Configured_120': cfg_120,
                    'Simulated_120': round(sim_120, 1),
                    'Delta_120': round(sim_120 - cfg_120, 1),
                    'Total_Meetings': total
                })
            except Exception as e:
                logger.warning(f"Could not analyze bias for room {room_id}: {e}")
        
        return pd.DataFrame(bias_data)

    def _get_meeting_rooms(self, sim_data: Dict, config_data: Dict) -> List[str]:
        """Return list of room IDs that are classified as gathering spaces."""
        gathering_types = self.config.get_space_types(self.config_name)['gathering']
        room_mapping = self.config.get_room_spacetype_mapping(self.config_name)
        room_to_spacetype = dict(zip(
            room_mapping['Room/Enclosure'].astype(str),
            room_mapping['Space Type']
        ))
        by_room = sim_data['by_room']
        return [
            room_id for room_id, spacetype in room_to_spacetype.items()
            if spacetype in gathering_types and room_id in by_room.columns
        ]
    
    def verify_meeting(self, sim_data: Dict, config_data: Dict) -> VerificationResult:
        """Compare configured versus simulated meeting length probabilities."""
        try:
            from scipy import ndimage
        except ImportError:
            logger.warning("scipy not installed, skipping meeting verification")
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        meeting_rooms = self._get_meeting_rooms(sim_data, config_data)
        if not meeting_rooms:
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        by_room = sim_data['by_room']
        simulated_distributions = {}
        
        for room_id in meeting_rooms:
            try:
                room_2d = self.processor.reshape_to_2d_days(by_room[room_id].tolist())
                room_2d = self.processor.apply_offhours_filter(room_2d)
                
                lengths = []
                for day_idx in range(room_2d.shape[1]):
                    occupied = room_2d[:, day_idx] > 0
                    labeled, num_features = ndimage.label(occupied)
                    for meeting_id in range(1, num_features + 1):
                        mask = labeled == meeting_id
                        lengths.append(np.sum(mask) * self.config.minutes_per_timestep)
                
                simulated_distributions[room_id] = {
                    30:  float(np.round(np.mean([l == 30 for l in lengths]) * 100)) if lengths else 0,
                    60:  float(np.round(np.mean([l == 60 for l in lengths]) * 100)) if lengths else 0,
                    90:  float(np.round(np.mean([l == 90 for l in lengths]) * 100)) if lengths else 0,
                    120: float(np.round(np.mean([l == 120 for l in lengths]) * 100)) if lengths else 0,
                }
            except Exception as e:
                logger.warning(f"Could not extract meeting metrics for room {room_id}: {e}")
                simulated_distributions[room_id] = {30: 0, 60: 0, 90: 0, 120: 0}
        
        simulated = pd.DataFrame.from_dict(simulated_distributions, orient='index')
        simulated.columns = [
            'probability of 30-min meetings',
            'probability of 60-min meetings',
            'probability of 90-min meetings',
            'probability of 120-min meetings',
        ]
        
        configured = self._extract_meeting_config_distributions(config_data, meeting_rooms)
        if configured.empty:
            return VerificationResult(pd.DataFrame(), simulated)
        
        common_rooms = simulated.index.intersection(configured.index)
        common_cols = simulated.columns.intersection(configured.columns)
        if not len(common_rooms) or not len(common_cols):
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        simulated = simulated.loc[common_rooms, common_cols].astype(float)
        configured = configured.loc[common_rooms, common_cols].astype(float)
        diff = simulated - configured
        
        return VerificationResult(configured, simulated, diff)
    
    def verify_meeting_full(self, sim_data: Dict, config_data: Dict) -> VerificationResult:
        """Compare all meeting parameters needed for pass/fail evaluation."""
        try:
            from scipy import ndimage
        except ImportError:
            logger.warning("scipy not installed, skipping meeting verification")
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        meeting_rooms = self._get_meeting_rooms(sim_data, config_data)
        if not meeting_rooms:
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        configured = self._extract_meeting_config_full(config_data, meeting_rooms)
        if configured.empty:
            return VerificationResult(pd.DataFrame(), pd.DataFrame())
        
        by_room = sim_data['by_room']
        simulated = pd.DataFrame(index=configured.index)
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        for room_id in meeting_rooms:
            try:
                room_2d = self.processor.reshape_to_2d_days(by_room[room_id].tolist())
                room_2d = self.processor.apply_offhours_filter(room_2d)
                
                lengths, meetings_per_day, occupants_per_meeting = [], [], []
                meeting_days = set()
                
                for day_idx in range(room_2d.shape[1]):
                    day_data = room_2d[:, day_idx]
                    occupied = day_data > 0
                    labeled, num_features = ndimage.label(occupied)
                    meetings_per_day.append(num_features)
                    
                    if num_features > 0:
                        meeting_days.add(days[day_idx % 7])
                    
                    for meeting_id in range(1, num_features + 1):
                        mask = labeled == meeting_id
                        lengths.append(np.sum(mask) * self.config.minutes_per_timestep)
                        occupants_per_meeting.append(float(day_data[mask][0]))
                
                simulated[room_id] = pd.Series({
                    'Days of week': ', '.join(sorted(meeting_days)),
                    'minimum number of meeting per day': int(np.min(meetings_per_day)) if meetings_per_day else 0,
                    'maximum number of meeting per day': int(np.max(meetings_per_day)) if meetings_per_day else 0,
                    'minimum number of people per meeting': int(np.min(occupants_per_meeting)) if occupants_per_meeting else 0,
                    'maximum number of people per meeting': int(np.max(occupants_per_meeting)) if occupants_per_meeting else 0,
                    'probability of 30-min meetings': float(np.round(np.mean([l == 30 for l in lengths]) * 100)) if lengths else 0,
                    'probability of 60-min meetings': float(np.round(np.mean([l == 60 for l in lengths]) * 100)) if lengths else 0,
                    'probability of 90-min meetings': float(np.round(np.mean([l == 90 for l in lengths]) * 100)) if lengths else 0,
                    'probability of 120-min meetings': float(np.round(np.mean([l == 120 for l in lengths]) * 100)) if lengths else 0,
                })
            except Exception as e:
                logger.warning(f"Could not extract full meeting metrics for room {room_id}: {e}")
        
        return VerificationResult(configured.T, simulated.T, diff=None)
    
    def _extract_meeting_config_distributions(self, config_data: Dict, meeting_rooms: List[str]) -> pd.DataFrame:
        """Extract configured meeting length probability distributions per room."""
        space_type_input = config_data['space_type_input']
        room_mapping = self.config.get_room_spacetype_mapping(self.config_name)
        room_to_spacetype = dict(zip(
            room_mapping['Room/Enclosure'].astype(str),
            room_mapping['Space Type']
        ))
        all_columns = list(space_type_input.columns)
        
        configured_df = pd.DataFrame()
        for room_id in meeting_rooms:
            space_type = room_to_spacetype.get(str(room_id))
            if not space_type or space_type not in all_columns:
                continue
            
            col_idx = all_columns.index(space_type)
            labels = space_type_input.iloc[1:, col_idx].tolist()
            values = space_type_input.iloc[1:, col_idx + 1].tolist()
            
            probs = {}
            for label, value in zip(labels, values):
                if pd.isna(label) or pd.isna(value):
                    continue
                label_str = str(label).strip().lower()
                if 'probability of 30-min meetings' in label_str:
                    probs['probability of 30-min meetings'] = float(value)
                elif 'probability of 60-min meetings' in label_str:
                    probs['probability of 60-min meetings'] = float(value)
                elif 'probability of 90-min meetings' in label_str:
                    probs['probability of 90-min meetings'] = float(value)
                elif 'probability of 120-min meetings' in label_str:
                    probs['probability of 120-min meetings'] = float(value)
            
            if probs:
                configured_df[room_id] = pd.Series(probs)
        
        return configured_df.T
    
    def _extract_meeting_config_full(self, config_data: Dict, meeting_rooms: List[str]) -> pd.DataFrame:
        """Extract all configured meeting parameters needed for pass/fail."""
        space_type_input = config_data['space_type_input']
        room_mapping = self.config.get_room_spacetype_mapping(self.config_name)
        room_to_spacetype = dict(zip(
            room_mapping['Room/Enclosure'].astype(str),
            room_mapping['Space Type']
        ))
        all_columns = list(space_type_input.columns)
        
        metric_keys = [
            'minimum number of meeting per day',
            'maximum number of meeting per day',
            'minimum number of people per meeting',
            'maximum number of people per meeting',
            'probability of 30-min meetings',
            'probability of 60-min meetings',
            'probability of 90-min meetings',
            'probability of 120-min meetings',
        ]
        
        configured_df = pd.DataFrame(index=['Days of week'] + metric_keys)
        
        for room_id in meeting_rooms:
            space_type = room_to_spacetype.get(str(room_id))
            if not space_type or space_type not in all_columns:
                continue
            
            col_idx = all_columns.index(space_type)
            labels = space_type_input.iloc[0:, col_idx].tolist()
            values = space_type_input.iloc[0:, col_idx + 1].tolist()
            
            room_params = {}
            for label, value in zip(labels, values):
                if pd.isna(label):
                    continue
                label_str = str(label).strip().lower()
                for key in metric_keys:
                    if key in label_str:
                        room_params[key] = value
                        break
            
            room_params.setdefault('Days of week', 'All')
            configured_df[room_id] = pd.Series(room_params)
        
        return configured_df


class PassFailEvaluator:
    """Evaluates whether simulated values pass or fail against configured targets."""
    
    def __init__(self, config: Config):
        self.config = config
        self.known_days = {
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
            'saturday', 'sunday', 'weekdays', 'all'
        }
    
    def evaluate_tolerance(self, result: VerificationResult) -> pd.DataFrame:
        """Return 1 where absolute difference is within tolerance, 0 otherwise."""
        if result.diff is None or result.diff.empty:
            return pd.DataFrame()
        return (result.diff.abs() <= self.config.tolerance).astype(int)
    
    def evaluate_behavior(self, result: VerificationResult, config_data: Dict,
                        extractor) -> pd.DataFrame:
        """Evaluate pass/fail for full behavior parameters."""
        configured, simulated = result.configured, result.simulated
        if configured.empty or simulated.empty:
            return pd.DataFrame()
        
        arrival_variation, departure_variation = extractor.get_arrival_departure_variation(config_data)
        
        passfail = pd.DataFrame(index=configured.index, columns=configured.columns)
        
        for job_type in configured.index:
            for param_label in configured.columns:
                cfg_val = configured.at[job_type, param_label]
                sim_val = simulated.at[job_type, param_label]
                param_lower = str(param_label).lower()
                
                try:
                    if 'day' in param_lower:
                        passfail.at[job_type, param_label] = self._days_match(cfg_val, sim_val)
                    elif 'arrival' in param_lower:
                        variation = arrival_variation.get(job_type, 0) * 60
                        passfail.at[job_type, param_label] = self._time_within(cfg_val, sim_val, variation)
                    elif 'departure' in param_lower:
                        variation = departure_variation.get(job_type, 0) * 60
                        passfail.at[job_type, param_label] = self._time_within(cfg_val, sim_val, variation)
                    else:
                        passfail.at[job_type, param_label] = (
                            1 if abs(float(sim_val) - float(cfg_val)) <= self.config.tolerance else 0
                        )
                except Exception as e:
                    logger.warning(f"Could not evaluate {job_type}/{param_label}: {e}")
                    passfail.at[job_type, param_label] = 0
        
        return passfail
    
    def evaluate_meeting(self, result: VerificationResult) -> pd.DataFrame:
        """Evaluate pass/fail for full meeting parameters."""
        configured, simulated = result.configured, result.simulated
        if configured.empty or simulated.empty:
            return pd.DataFrame()
        
        passfail = pd.DataFrame(index=configured.index, columns=configured.columns)
        
        for room_id in configured.index:
            for metric_label in configured.columns:
                cfg_val = configured.at[room_id, metric_label]
                sim_val = simulated.at[room_id, metric_label]
                metric_lower = str(metric_label).lower()
                
                try:
                    is_meeting_metric = 'meeting' in metric_lower and 'people' not in metric_lower
                    is_people_metric = 'people' in metric_lower
                    is_day_metric = 'day' in metric_lower and not is_meeting_metric and not is_people_metric
                    
                    if is_day_metric:
                        passfail.at[room_id, metric_label] = 1
                    elif 'minimum' in metric_lower and is_meeting_metric:
                        passfail.at[room_id, metric_label] = 1 if float(sim_val) >= float(cfg_val) else 0
                    elif 'maximum' in metric_lower and is_meeting_metric:
                        passfail.at[room_id, metric_label] = 1 if float(sim_val) <= float(cfg_val) else 0
                    elif 'minimum' in metric_lower and is_people_metric:
                        passfail.at[room_id, metric_label] = 1 if float(sim_val) >= float(cfg_val) else 0
                    elif 'maximum' in metric_lower and is_people_metric:
                        passfail.at[room_id, metric_label] = 1 if float(sim_val) <= float(cfg_val) else 0
                    elif 'probability' in metric_lower:
                        passfail.at[room_id, metric_label] = (
                            1 if abs(float(sim_val) - float(cfg_val)) <= self.config.tolerance else 0
                        )
                    else:
                        passfail.at[room_id, metric_label] = 1
                except Exception as e:
                    logger.warning(f"Could not evaluate {room_id}/{metric_label}: {e}")
                    passfail.at[room_id, metric_label] = 0
        
        return passfail
    
    def _days_match(self, cfg_val, sim_val) -> int:
        """Compare day-of-week lists, treating 'Weekdays' as equivalent to the full list."""
        if pd.isna(cfg_val) or pd.isna(sim_val):
            return 0
        
        cfg_str = str(cfg_val).strip().lower()
        sim_str = str(sim_val).strip().lower()
        
        if cfg_str in ('weekdays', 'weekday'):
            cfg_str = 'monday,tuesday,wednesday,thursday,friday'
        if sim_str in ('weekdays', 'weekday'):
            sim_str = 'monday,tuesday,wednesday,thursday,friday'
        
        cfg_days = [d.strip() for d in cfg_str.split(',')]
        sim_days = [d.strip() for d in sim_str.split(',')]
        
        return 1 if set(cfg_days) == set(sim_days) else 0
    
    def _time_to_seconds(self, t) -> float:
        """Convert an HH:MM time string into seconds since midnight."""
        if pd.isna(t):
            return 0.0
        
        try:
            time_str = str(t).strip()
            if ':' in time_str:
                parts = time_str.split(':')
                hours = float(parts[0])
                minutes = float(parts[1]) if len(parts) > 1 else 0
                return hours * 3600 + minutes * 60
            return float(time_str)
        except Exception:
            logger.warning(f"Invalid time format '{t}'. Expected HH:MM. Using 00:00 instead.")
            return 0.0
    
    def _time_within(self, cfg_val, sim_val, variation_seconds: float) -> int:
        """Return 1 if simulated time is within the allowed variation window of configured time."""
        cfg_secs = self._time_to_seconds(cfg_val)
        sim_secs = self._time_to_seconds(sim_val)
        return 1 if abs(cfg_secs - sim_secs) <= variation_seconds else 0