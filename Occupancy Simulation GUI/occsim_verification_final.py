import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from xml.etree import ElementTree
from openpyxl import Workbook
from skimage import measure
# Comment

# Set random seed for reproducibility in plotting libraries
np.random.seed(0)

class OccVer:
    """
    A class for verifying occupancy simulation focused on generating % difference heatmaps
    and pass/fail heatmaps for given configurations.
    """
    def __init__(self, config: str, obconfig: str = "fullyear"):
        """
        Initialize the OccVer class with configuration and data file paths.
        Args:
            config (str): Configuration name (e.g., 'hflm_TYPI').
            obconfig (str): Occupancy simulation configuration ('fullyear' or '52weeks').
        """
        self.config = config
        self.obconfig = obconfig
        
        # Define input file paths for configuration, using 'simulation_results' as base directory
        self.xml_file = f'simulation_results/{config}/output_xml.xml'
        if obconfig == 'fullyear':
            self.occsim_byroom = f'simulation_results/{config}/occSim.csv'
        elif obconfig == '52weeks':
            self.occsim_byroom = f'simulation_results/{config}/occSim_cat.csv'
        self.occsim_byocc = f'simulation_results/{config}/occSim_by_Occupant.csv'
        self.input = f'OOS/config_files/input_{config}.xlsx'
        # Define output directories for organized results
        self.base_out = os.path.join('./Verification_Results', self.config)
        self.hm_out = os.path.join(self.base_out, '%Diff Heatmaps')  # Heatmap results
        self.hm_data_out = os.path.join(self.hm_out, '%Diff Calcs Excel Data')  # CSV data for heatmaps
        self.pf_out = os.path.join(self.base_out, 'Pass-Fail Heatmaps')  # Pass/Fail results
        self.pf_data_out = os.path.join(self.pf_out, 'Pass-Fail_Calcs_Excel Data')  # CSV data for pass/fail
        self.check_calc_out = './Verification_calcs_excel_data'  # Folder for verification calculation CSVs
        self._ensure_dirs()  # Call to create directories

    def _ensure_dirs(self):
        """Create output directories if they don't exist."""
        os.makedirs(self.hm_out, exist_ok=True)
        os.makedirs(self.hm_data_out, exist_ok=True)
        os.makedirs(self.pf_out, exist_ok=True)
        os.makedirs(self.pf_data_out, exist_ok=True)
        os.makedirs(self.check_calc_out, exist_ok=True)

    def load_file(self, file: str) -> pd.DataFrame:
        """
        Load data from CSV files based on the specified file type.
        Args:
            file (str): Type of file to load ('OccSim' or 'OccSimOcc').
        Returns:
            pd.DataFrame: Loaded data as a DataFrame.
        """
        if file == 'OccSim':
            data = pd.read_csv(self.occsim_byroom)
            if data.columns[-1] != 'Whole building':
                data.drop(columns=[data.columns[-1]], inplace=True)
        elif file == 'OccSimOcc':
            data = pd.read_csv(self.occsim_byocc, skiprows=lambda x: x in range(6)).iloc[:, 0:-1]
        return data

    def get_days_2D(self, yearlist: list, timestep: int = 12) -> np.ndarray:
        """
        Reshape a yearly list into a 2D array of days.
        Args:
            yearlist (list): List of yearly data.
            timestep (int): Number of time steps per hour (default=12).
        Returns:
            np.ndarray: 2D array of shape [24*timestep, numdays].
        """
        days_2D = np.reshape(yearlist, [24 * timestep, int(len(yearlist) / (24 * timestep))], order='F')
        return days_2D

    def offhours_filter(self, arr: np.ndarray, val: int = 0) -> np.ndarray:
        """
        Filter out off-hours data by setting specific time ranges to a given value.
        Args:
            arr (np.ndarray): Input 2D array to filter.
            val (int): Value to set for off-hours (default=0).
        Returns:
            np.ndarray: Filtered array.
        """
        arr[0:72, :] = val  # Early hours (midnight to 6 AM)
        arr[252:288, :] = val  # Late hours (9 PM to midnight)
        return arr

    def get_individual_days(self, yearlist: list, startday: str = 'Sunday', offhours_filter: int = 1) -> dict:
        """
        Split yearly data into individual days of the week.
        Args:
            yearlist (list): Yearly data list.
            startday (str): Starting day of the week (default='Sunday').
            offhours_filter (int): Whether to apply off-hours filter (default=1).
        Returns:
            dict: Dictionary mapping day names to their respective data arrays.
        """
        DAYS = {}
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        days_2D = self.get_days_2D(yearlist=yearlist)
        for d in range(7):
            if offhours_filter:
                DAYS[days[d]] = self.offhours_filter(days_2D[:, d::7])
        return DAYS

    def get_days_presence(self, yearlist: list) -> list:
        """
        Identify days with occupancy greater than zero.
        Args:
            yearlist (list): Yearly data list.
        Returns:
            list: List of days with occupancy.
        """
        DAYS = self.get_individual_days(yearlist=yearlist)
        meetday = []
        for d in DAYS.keys():
            if np.sum(np.sum(DAYS[d])) > 0:
                meetday.append(d)
        return meetday

    def get_OccInfo(self) -> pd.DataFrame:
        """
        Extract occupant information (ID, job type, office) from XML output.
        Returns:
            pd.DataFrame: DataFrame with occupant details.
        """
        tree = ElementTree.parse(self.xml_file)
        occtype = []
        simroom = []
        for occ in tree.getroot().find('Occupants'):
            simroom.append('_'.join(occ.get('ID').split('_')[0:-1]))
            occtype.append(occ.find('JobType').text)
        occInfo = {'Occupant': list(range(len(simroom))), 'Office': simroom, 'Job Type': occtype}
        return pd.DataFrame.from_dict(occInfo)

    def determine_meeting_or_office(self) -> tuple:
        """
        Determine whether spaces are offices or meeting rooms based on input data.
        Returns:
            tuple: Lists of meeting rooms and offices.
        """
        offices = []
        meeting_rooms = []
        space_type_input_df = pd.read_excel(self.input, sheet_name='space_type_input')
        for i in range(int(len(space_type_input_df.columns) / 2)):
            sliced_columns = space_type_input_df.iloc[:, 2 * i:(2 * i + 2)]
            space_name = sliced_columns.columns[0]
            first_row = sliced_columns[space_name].iloc[0]
            if first_row.split(':')[0] == 'Office':
                offices.append(space_name)
            else:
                meeting_rooms.append(space_name)
        return meeting_rooms, offices

    def convert_column_title_to_str(self, init_cols: list) -> list:
        """
        Convert column titles to string format.
        Args:
            init_cols (list): Initial column titles.
        Returns:
            list: Column titles as strings.
        """
        return [str(col) for col in init_cols]

    def get_allrooms_sptype(self) -> pd.DataFrame:
        """
        Map rooms to their space types based on input data.
        Returns:
            pd.DataFrame: DataFrame mapping rooms to space types.
        """
        roomnumber = pd.read_csv(self.occsim_byocc, skiprows=lambda x: x not in [2]).columns[0:-1]
        roomid = list(pd.read_csv(self.occsim_byocc, skiprows=lambda x: x not in [3]).columns[0:-1])
        meeting_rooms, offices = self.determine_meeting_or_office()
        df2 = pd.read_excel(self.input, sheet_name='space_input')
        rooms = df2['Room/Enclosure']
        sptypes = []
        occsim_roomnum = []
        occsim_sptypes = []
        for room in rooms:
            sptype = df2['Space Type'].loc[df2['Room/Enclosure'] == room].values[0]
            sptypes.append(sptype)
            occsim_roomnum.append(roomnumber[list(roomid).index(str(room))])
            if sptype in meeting_rooms:
                occsim_sptypes.append('Gathering')
            elif sptype in offices:
                occsim_sptypes.append('Office')
            else:
                occsim_sptypes.append('Other')
        RS = pd.DataFrame({'rooms': rooms, 'sptypes': sptypes, 'occsim_roomids': occsim_roomnum, 'occsim_sptypes': occsim_sptypes})
        RS['rooms'] = self.convert_column_title_to_str(RS['rooms'])
        return RS

    def get_configured_occupant_types(self) -> pd.DataFrame:
        """
        Retrieve configured occupant types from input Excel.
        Returns:
            pd.DataFrame: DataFrame of occupant types per office.
        """
        meeting_rooms, offices = self.determine_meeting_or_office()
        space_type_input_df = pd.read_excel(self.input, sheet_name='space_type_input')
        PD = pd.DataFrame()
        cols = list(space_type_input_df.columns)
        for o in offices:
            idx = cols.index(o)
            PD[o] = space_type_input_df.iloc[1::, idx + 1]
        lbls = []
        for l in space_type_input_df[o]:
            try:
                lbls.append(l.split(':')[-1].split('-')[-1].split('[')[0].strip())
            except:
                lbls.append(l)
        PD.insert(0, 'labels', lbls[1::])
        PD.set_index('labels', inplace=True)
        PD = PD.sort_index(axis=0, ascending=True, inplace=False, kind='quicksort')
        PD = PD.dropna(how='all')
        return PD

    def office_breakdown(self, generate_check_files: bool = False) -> pd.DataFrame:
        """
        Associate occupants with their assigned offices and compute distribution of job types.
        Args:
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            pd.DataFrame: DataFrame with percentage distribution of occupant types per office.
        """
        RS = self.get_allrooms_sptype()
        occInfo = self.get_OccInfo()
        sptypes = []
        for rm in occInfo['Office']:
            sptypes.append(list(RS['sptypes'].loc[RS['rooms'] == str(rm)])[0])
        OI = pd.DataFrame()
        OI['Office'] = sptypes
        OI['Occupant Type'] = occInfo['Job Type']
        PD = self.get_configured_occupant_types()
        D = pd.DataFrame()
        D['occtypes'] = PD.index
        D_count = D.copy()
        for off in list(set(OI['Office'])):
            occtypes = OI['Occupant Type'].loc[OI['Office'] == off]
            temp2 = []
            for ot in PD.index:
                count = np.sum(occtypes == ot)
                temp2.append(count)
            D[off] = temp2 / np.sum(temp2) * 100
            D_count[off] = temp2
        D.set_index('occtypes', inplace=True)
        if generate_check_files:
            D.to_csv(os.path.join(self.check_calc_out, 'Office_Distribution.csv'))
            D_count.to_csv(os.path.join(self.check_calc_out, 'Office_Distribution_Count.csv'), index=False)
        return D

    def verify_office_breakdown(self) -> pd.DataFrame:
        """
        Compare configured vs. simulated office occupant distribution.
        Returns:
            pd.DataFrame: Combined DataFrame of configured and simulated distributions.
        """
        D = self.office_breakdown()
        PD = self.get_configured_occupant_types()
        COMB = pd.DataFrame()
        for off in PD.columns:
            COMB[f'{off}: Configured'] = list(PD[off])
            COMB[f'{off}: Simulated'] = list(D[off])
        COMB['occtypes'] = list(D.index)
        COMB.set_index('occtypes', inplace=True)
        return COMB

    def get_arrival_departure(self, yearlist: list) -> tuple:
        """
        Calculate arrival and departure times from yearly data.
        Args:
            yearlist (list): Yearly occupancy data.
        Returns:
            tuple: Lists of arrival and departure times.
        """
        days_2D = self.offhours_filter(self.get_days_2D(yearlist), val=-1)
        presence = days_2D >= 0
        change_presence = np.diff(presence, n=1, axis=0, prepend=0).astype(int)
        arrivals = []
        departures = []
        for day in range(len(days_2D[0, :])):
            temp = change_presence[:, day]
            arrs = np.where(temp == 1)[0]
            deps = np.where(temp == -1)[0]
            if len(arrs):
                arrivals.append(np.min(arrs))
            if len(deps):
                departures.append(np.max(deps))
        return arrivals, departures

    def arrival_departure_stats(self, offhours_filter=1) -> pd.DataFrame:
        """
        Compute median arrival and departure times per occupant type.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (unused here but kept for compatibility).
        Returns:
            pd.DataFrame: DataFrame with arrival and departure medians per occupant type.
        """
        occSimOcc = self.load_file('OccSimOcc')
        occInfo = self.get_OccInfo()
        OT = {ot: [] for ot in set(occInfo['Job Type'])}
        AD = pd.DataFrame()
        for i in range(len(occInfo['Occupant'])):
            OT[occInfo['Job Type'].iloc[i]].append(occInfo['Occupant'].iloc[i])
        for ot in sorted(OT.keys()):
            arrivals = []
            departures = []
            for o in OT[ot]:
                a, d = self.get_arrival_departure(occSimOcc[str(o)])
                arrivals.extend(a)
                departures.extend(d)
            AD[ot] = [int(np.round(np.median(arrivals))), int(np.round(np.median(departures)))]
        AD['index'] = ['Arrival', 'Departure']
        AD.set_index('index', inplace=True)
        return AD

    def get_configured_occ_behavior(self, offhours_filter=1) -> pd.DataFrame:
        """
        Retrieve configured occupant behavior from input Excel.
        Args:
            offhours_filter (int): Unused but kept for compatibility.
        Returns:
            pd.DataFrame: DataFrame of configured behavior parameters.
        """
        behavior_input_df = pd.read_excel(self.input, sheet_name='behavior_input')
        occtypes = list(behavior_input_df.columns[0::2])
        PD = pd.DataFrame()
        cols = list(behavior_input_df.columns)
        for o in occtypes:
            idx = cols.index(o)
            PD[o] = behavior_input_df.iloc[1::, idx + 1]
        lbls = []
        for l in behavior_input_df.iloc[:, 0]:
            try:
                lbls.append(l.split('[')[0].split(':')[-1].strip())
            except:
                lbls.append(l)
        PD.insert(0, 'labels', lbls[1::])
        PD.set_index('labels', inplace=True)
        return PD

    def simroom_mapping(self) -> pd.DataFrame:
        """
        Map simulated room numbers to IDs and names.
        Returns:
            pd.DataFrame: DataFrame mapping room numbers, IDs, and space types.
        """
        roomnumber = pd.read_csv(self.occsim_byocc, skiprows=lambda x: x not in [2]).columns[0:-1]
        roomid = list(pd.read_csv(self.occsim_byocc, skiprows=lambda x: x not in [3]).columns[0:-1])
        roomname = [self.get_room_occsim_spacetype(rn)[0] for rn in roomid[2:-1]]
        simroom_map = pd.DataFrame()
        simroom_map['roomnumber'] = roomnumber[1::]
        simroom_map['roomid'] = roomid[1::]
        simroom_map['roomname'] = ['Outdoor'] + roomname + ['Away']
        return simroom_map

    def get_room_occsim_spacetype(self, room: str) -> list:
        """
        Determine the simulated space type for a given room.
        Args:
            room (str): Room identifier.
        Returns:
            list: Space type as a list (e.g., ['Gathering']).
        """
        df2 = pd.read_excel(self.input, sheet_name='space_input')
        try:
            sp = df2['Space Type'].loc[df2['Room/Enclosure'] == room].values
            if not len(sp):
                sp = df2['Space Type'].loc[df2['Room/Enclosure'] == int(room)].values
        except Exception:
            sp = ''
        Gathering = ['Large Conference With Breakroom', 'Office Assistance Manager Conference', 'Phone Conference',
                     'Quiet', 'Medium Conference', 'Large Meeting Booth', 'Break', 'Mothers',
                     'IT Assistance Conference', 'Small Conference', 'Large Conference', 'Small Meeting Booth', 'Director Conference']
        Offices = ['Office Assistance Manager Cubicle', 'Private Office', 'Storage Misc Office',
                   'IT Assistance Cubicle', 'Open Office', 'Director Office']
        if sp in Gathering:
            sp = ['Gathering']
        elif sp in Offices:
            sp = ['Offices']
        return sp

    def sptype_distribution_by_occtype(self, offhours_filter=1, generate_check_files: bool = False) -> tuple:
        """
        Compute distribution of occupant types across space types.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (unused but kept for compatibility).
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            tuple: DataFrames of space type distribution and days of presence per occupant type.
        """
        occSimOcc = self.load_file('OccSimOcc')
        RS = self.get_allrooms_sptype()
        occInfo = self.get_OccInfo()
        simroom_map = self.simroom_mapping()
        os_sptypes = simroom_map['roomname']
        for i in range(1, len(os_sptypes) - 1):
            rm = simroom_map['roomid'][i]
            osp = RS['occsim_sptypes'].loc[RS['rooms'] == rm]
            os_sptypes[i] = list(osp)[0]
        simroom_map['roomname'] = os_sptypes
        own_office = {}
        occs = occInfo['Occupant']
        for occ in occs:
            office_sp = list(occInfo['Office'].loc[occInfo['Occupant'] == occ])[0]
            office_sim = list(simroom_map['roomnumber'].loc[simroom_map['roomid'] == office_sp])[0]
            own_office[occ] = office_sim
        data = occSimOcc.iloc[:, 2::]
        num_rooms = np.max(np.max(data))
        rooms_occs = np.zeros((num_rooms + 1, np.shape(data)[1]))
        for i in range(0, num_rooms + 1):
            temp = np.sum(data == i, axis=0)
            rooms_occs[i, :] = temp
        OT = {ot: [] for ot in set(occInfo['Job Type'])}
        ST = {st: [] for st in set(simroom_map['roomname'].iloc[0:-1])}
        for i in range(len(occInfo['Occupant'])):
            OT[occInfo['Job Type'].iloc[i]].append(occInfo['Occupant'].iloc[i])
        for i in range(len(simroom_map['roomname'].iloc[0:-1])):
            ST[simroom_map['roomname'].iloc[i]].append(simroom_map['roomnumber'].iloc[i])
        rooms_occs_copy = rooms_occs.copy()
        oo_perc = np.zeros((1, len(own_office.keys())))
        for occ in own_office.keys():
            room = int(own_office[occ])
            oo_perc[0, occ] = rooms_occs[room, occ]
            rooms_occs[room, occ] = 0
        ST['Own Office'] = [num_rooms + 1]
        rooms_occs = np.append(rooms_occs, oo_perc, axis=0)
        rooms_occs = pd.DataFrame(rooms_occs)
        rooms_occs.columns = data.columns
        OT_DAYS = pd.DataFrame()
        days_ot = []
        DF_OT = pd.DataFrame()
        for ot in OT.keys():
            cols = [str(o) for o in OT[ot]]
            temp_occ = np.array(occSimOcc[cols])
            temp_occ[temp_occ == -1] = 0
            temp_occ = np.sum(temp_occ, axis=1)
            days_ot.append(", ".join(self.get_days_presence(yearlist=temp_occ)))
            temp = []
            for st in ST.keys():
                vals = [int(s) for s in ST[st]]
                arr1 = rooms_occs.iloc[vals, OT[ot]]
                temp.append(np.sum(np.sum(arr1)))
            DF_OT[ot] = temp
        OT_DAYS['ot'] = OT.keys()
        OT_DAYS['Days'] = days_ot
        OT_DAYS.set_index('ot', inplace=True)
        OT_DAYS = OT_DAYS.sort_index(axis=0, ascending=True, inplace=False, kind='quicksort')
        DF_OT['space types'] = list(ST.keys())
        DF_OT.set_index('space types', inplace=True)
        DF_OT = np.round(DF_OT / np.sum(DF_OT, axis=0) * 100)
        sorted_cols = sorted(DF_OT.columns)
        DF_OT = DF_OT[sorted_cols]
        if generate_check_files:
            OT_DAYS.to_csv(os.path.join(self.check_calc_out, 'OT_DAYS.csv'))
            DF_OT.T.to_csv(os.path.join(self.check_calc_out, 'DF_OT.csv'))
        return DF_OT, OT_DAYS

    def get_simulated_occ_behavior(self, generate_check_files: bool = False) -> pd.DataFrame:
        """
        Compute simulated occupant behavior based on data.
        Args:
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            pd.DataFrame: Combined DataFrame of configured and simulated behavior.
        """
        CONFIG = self.get_configured_occ_behavior()
        DF_OT, OT_DAYS = self.sptype_distribution_by_occtype(generate_check_files=generate_check_files)
        AD = self.arrival_departure_stats()
        occSimOcc = self.load_file('OccSimOcc')
        Times = [t.split(' ')[-1] for t in occSimOcc['Time'].iloc[0:288]]
        SIM = pd.DataFrame()
        SIM['labels'] = list(CONFIG.index)
        for ot in sorted(CONFIG.columns):
            if ot in DF_OT.columns:
                days = ','.join(list(OT_DAYS.loc[ot]))
                arrival = Times[AD[ot].loc['Arrival']]
                departure = Times[AD[ot].loc['Departure']]
                own_office_perc = DF_OT[ot].loc['Own Office']
                other_office_perc = DF_OT[ot].loc['Office']
                meeting_perc = DF_OT[ot].loc['Gathering']
                other_perc = DF_OT[ot].loc['Other']
                outdoor_perc = DF_OT[ot].loc['Outdoor']
                try:
                    SIM[ot] = [days, arrival, 0, departure, 0, own_office_perc, 0, other_office_perc, 0,
                               meeting_perc, 0, other_perc, 0, outdoor_perc, 0, 0, 0, 0, 0]
                except:
                    SIM[ot] = [days, arrival, 0, departure, 0, own_office_perc, 0, other_office_perc, 0,
                               meeting_perc, 0, other_perc, 0, outdoor_perc, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            else:
                SIM[ot] = [''] * len(CONFIG.index)
        SIM.set_index('labels', inplace=True)
        COMB = pd.DataFrame()
        COMB.index = SIM.index
        for o in CONFIG.columns:
            COMB[f'{o}: Configured'] = list(CONFIG[o])
            COMB[f'{o}: Simulated'] = list(SIM[o])
        if generate_check_files:
            COMB.T.to_csv(os.path.join(self.check_calc_out, 'Behavior_Input_Comparison.csv'))
        return COMB
    
    def analyze_behavior_underuse_destinations(self,
                                               generate_check_files: bool = False
                                               ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        For each occupant type, analyze where time goes when simulated % time in a space
        is below the configured %.

        Returns:
            diff_df: DataFrame [space_type x occupant_type] of (simulated - configured) percentages.
            underuse_summary: DataFrame with one row per (occupant_type, underused_space),
                              listing spaces where time increased (positive deltas).

        Notes:
            - Uses get_configured_occ_behavior() for configured behavior.
            - Uses sptype_distribution_by_occtype() for simulated distribution.
            - Space types considered: Own Office, Office, Gathering, Other, Outdoor.
        """
        # 1) Configured behavior
        CONFIG = self.get_configured_occ_behavior()

        def _find_config_row(label_index, keyword):
            candidates = [lbl for lbl in label_index if keyword.lower() in str(lbl).lower()]
            return candidates[0] if candidates else None

        row_own_office   = _find_config_row(CONFIG.index, "own office")
        row_other_office = _find_config_row(CONFIG.index, "other office")
        row_gathering    = _find_config_row(CONFIG.index, "gathering")
        # 'other' matches both "Other" and "Other Office"; order above matters
        row_other        = _find_config_row(CONFIG.index, "other")  
        row_outdoor      = _find_config_row(CONFIG.index, "outdoor")

        # 2) Simulated distribution by space type and occupant type
        DF_OT, OT_DAYS = self.sptype_distribution_by_occtype()
        space_map = {
            "Own Office": "Own Office",
            "Office": "Office",
            "Gathering": "Gathering",
            "Other": "Other",
            "Outdoor": "Outdoor"
        }

        occ_types = sorted(CONFIG.columns)
        space_types = list(space_map.keys())

        cfg_mat = pd.DataFrame(index=space_types, columns=occ_types, dtype=float)
        sim_mat = pd.DataFrame(index=space_types, columns=occ_types, dtype=float)

        for ot in occ_types:
            # Configured values
            if row_own_office is not None:
                cfg_mat.at["Own Office", ot] = CONFIG.at[row_own_office, ot]
            if row_other_office is not None:
                cfg_mat.at["Office", ot] = CONFIG.at[row_other_office, ot]
            if row_gathering is not None:
                cfg_mat.at["Gathering", ot] = CONFIG.at[row_gathering, ot]
            if row_other is not None:
                cfg_mat.at["Other", ot] = CONFIG.at[row_other, ot]
            if row_outdoor is not None:
                cfg_mat.at["Outdoor", ot] = CONFIG.at[row_outdoor, ot]

            # Simulated values (if occupant type present in DF_OT)
            if ot in DF_OT.columns:
                for st_sim, st_std in space_map.items():
                    if st_sim in DF_OT.index:
                        sim_mat.at[st_std, ot] = DF_OT.at[st_sim, ot]

        # 3) Differences (simulated - configured)
        diff_df = sim_mat - cfg_mat

        # 4) Under-use destinations
        rows_summary = []
        for ot in occ_types:
            for st in space_types:
                cfg_val = cfg_mat.at[st, ot]
                sim_val = sim_mat.at[st, ot]
                diff_val = diff_df.at[st, ot]
                if pd.isna(cfg_val) or pd.isna(sim_val):
                    continue
                if diff_val < 0:
                    dests = []
                    for st2 in space_types:
                        if diff_df.at[st2, ot] > 0:
                            dests.append(f"{st2} (+{diff_df.at[st2, ot]:.1f}%)")
                    rows_summary.append({
                        "OccupantType": ot,
                        "UnderusedSpace": st,
                        "ConfiguredPct": cfg_val,
                        "SimulatedPct": sim_val,
                        "DeltaPct": diff_val,
                        "WhereTimeWent": "; ".join(dests)
                    })

        underuse_summary = pd.DataFrame(rows_summary)

        if generate_check_files:
            os.makedirs(self.check_calc_out, exist_ok=True)

            # 1) diff_df to an Excel file with one sheet per config
            diff_outpath = os.path.join(self.check_calc_out,
                                        "Behavior_SpaceType_Diff_SimMinusConfig.xlsx")
            sheet_name = self.config
            if not os.path.exists(diff_outpath):
                with pd.ExcelWriter(diff_outpath, engine='openpyxl') as writer:
                    diff_df.to_excel(writer, sheet_name=sheet_name)
            else:
                with pd.ExcelWriter(diff_outpath, engine='openpyxl', mode='a',
                                    if_sheet_exists='replace') as writer:
                    diff_df.to_excel(writer, sheet_name=sheet_name)

            # 2) underuse_summary to a separate Excel file, also one sheet per config
            underuse_outpath = os.path.join(self.check_calc_out,
                                            "Behavior_SpaceType_Underuse_Destinations.xlsx")
            if not os.path.exists(underuse_outpath):
                with pd.ExcelWriter(underuse_outpath, engine='openpyxl') as writer:
                    underuse_summary.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                with pd.ExcelWriter(underuse_outpath, engine='openpyxl', mode='a',
                                    if_sheet_exists='replace') as writer:
                    underuse_summary.to_excel(writer, sheet_name=sheet_name, index=False)

        return diff_df, underuse_summary

    def verify_meeting_parameters(self, offhours_filter=1) -> dict:
        """
        Verify meeting parameters from simulated data.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1).
        Returns:
            dict: Dictionary of meeting parameters (count, length, occupants, days).
        """
        occSim = self.load_file('OccSim')
        RS = self.get_allrooms_sptype()
        rooms = list(RS['rooms'].loc[RS['occsim_sptypes'] == 'Gathering'])
        CountMeetings = pd.DataFrame()
        LengthMeetings = {}
        CountOccs = {}
        MeetingDays = {}
        for room in rooms:
            daycount = []
            try:
                yearlist = occSim[room]
            except:
                yearlist = occSim[str(room)]
            days_2D = self.get_days_2D(yearlist=yearlist)
            if offhours_filter:
                days_2D = self.offhours_filter(days_2D)
            DAYS = self.get_individual_days(yearlist=yearlist)
            meetday = []
            for d in DAYS.keys():
                if np.sum(np.sum(DAYS[d])) > 0:
                    meetday.append(d)
            length_meetings = []
            count_occs = []
            for day in range(np.shape(days_2D)[1]):
                temp = days_2D[:, day]
                groups, group_count = measure.label(temp > 0, return_num=True, connectivity=1)
                daycount.append(group_count)
                for i in range(1, group_count + 1):
                    length_meetings.append(np.sum(groups == i) * 5)
                    count_occs.append(temp[groups == i][0])
            CountMeetings[room] = daycount
            LengthMeetings[room] = length_meetings
            CountOccs[room] = count_occs
            MeetingDays[room] = meetday
        Meeting_Params = {'CountMeetings': CountMeetings, 'LengthMeetings': LengthMeetings,
                          'CountOccupants': CountOccs, 'MeetingDays': MeetingDays}
        return Meeting_Params

    def table_Meetings_Ver(self, offhours_filter=1, generate_check_files: bool = False) -> pd.DataFrame:
        """
        Generate additional statistics about meeting data.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1).
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            pd.DataFrame: DataFrame with meeting length statistics.
        """
        outdir = self.check_calc_out
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        Meeting_Params = self.verify_meeting_parameters(offhours_filter)
        Ver = pd.DataFrame()
        Ver['rooms'] = Meeting_Params['CountMeetings'].keys()
        Ver['total_meetings_in_year'] = list(np.sum(Meeting_Params['CountMeetings'], axis=0))
        Ver['max_meetings_in_one_day'] = list(np.max(Meeting_Params['CountMeetings'], axis=0))
        meeting_hours = []
        ave_occ_count = []
        max_occ_count = []
        meeting_lengths = []
        ML = {}
        for key in Meeting_Params['LengthMeetings'].keys():
            temp = [k for k in Meeting_Params['LengthMeetings'][key] if k > 0]
            meeting_hours.append(np.sum(Meeting_Params['LengthMeetings'][key]))
            meeting_lengths.append(np.mean(temp))
            ML[key] = {}
            lst = Meeting_Params['LengthMeetings'][key]
            for k in list(set(lst)):
                ML[key][k] = np.round(np.mean(lst == k) * 100)
            ave_occ_count.append(np.mean(Meeting_Params['CountOccupants'][key]))
            max_occ_count.append(np.max(Meeting_Params['CountOccupants'][key]))
        ML = pd.DataFrame(ML).sort_index(axis=0, ascending=True, inplace=False, kind='quicksort')
        ML = ML.fillna(0)
        if generate_check_files:
            ML.to_csv(os.path.join(outdir, 'Meeting_Times_Simulated.csv'))
        Ver['ave_meeting_length'] = meeting_lengths
        Ver['max_occs_in_single_meeting'] = max_occ_count
        Ver['ave_occs_in_single_meeting'] = ave_occ_count
        Ver['total_occupied_hours_in_year'] = meeting_hours
        return ML
    
    def analyze_meeting_length_bias(self,
                                    offhours_filter: int = 1,
                                    generate_check_files: bool = False
                                    ) -> pd.DataFrame:
        """
        Analyze whether simulated meetings prioritize 120-minute meetings over 60-minute meetings,
        by comparing simulated meeting length distributions to configured distributions.

        Also records, for each room, how many meetings there were at each meeting length.

        Returns:
            summary_df: DataFrame indexed by room with:
                - configured_pct_60, simulated_pct_60, delta_60
                - configured_pct_120, simulated_pct_120, delta_120
                - ratio_120_to_60_config, ratio_120_to_60_sim
                - bias_120_vs_60 (True if 120-min meetings are more overrepresented than 60-min)
                - total_meetings
                - count_len_<L> for each meeting length L observed (e.g., count_len_30, count_len_60, ...)
        """
        # 1) Simulated meeting length distribution (percentages) per room
        ML_sim = self.table_Meetings_Ver(offhours_filter=offhours_filter,
                                         generate_check_files=generate_check_files)

        # 2) Raw meeting parameters => list of lengths per room
        Meeting_Params = self.verify_meeting_parameters(offhours_filter)
        length_by_room = Meeting_Params['LengthMeetings']

        # 3) Configured meeting parameters (per room)
        MTG_cfg = self.get_configured_space_parameters(generate_check_files=generate_check_files)
        MTG_cfg = MTG_cfg.set_index('labels')

        # Helper: find row in MTG_cfg.index for a given duration (60, 120)
        def _find_row_for_duration(labels_index, minutes):
            candidates = [lbl for lbl in labels_index
                          if str(minutes) in str(lbl) and 'min' in str(lbl).lower()]
            if not candidates:
                return None
            return candidates[0]

        row_60 = _find_row_for_duration(MTG_cfg.index, 60)
        row_120 = _find_row_for_duration(MTG_cfg.index, 120)

        if row_60 is None or row_120 is None:
            print("Warning: could not automatically locate configured rows for 60 and/or 120-minute meetings "
                  "in 'space_type_input'. Please adjust analyze_meeting_length_bias() row selection.")

        summary_rows = {}
        all_lengths = set()

        for room in ML_sim.columns:
            # --- Simulated percentages ---
            sim_pct_60 = ML_sim.at[60, room] if 60 in ML_sim.index else np.nan
            sim_pct_120 = ML_sim.at[120, room] if 120 in ML_sim.index else np.nan

            # --- Configured percentages ---
            cfg_col = f"{room}: Configured"
            if cfg_col in MTG_cfg.columns:
                cfg_pct_60 = MTG_cfg.at[row_60, cfg_col] if row_60 is not None else np.nan
                cfg_pct_120 = MTG_cfg.at[row_120, cfg_col] if row_120 is not None else np.nan
            else:
                cfg_pct_60 = np.nan
                cfg_pct_120 = np.nan

            # --- Deltas ---
            delta_60 = (sim_pct_60 - cfg_pct_60
                        if not (pd.isna(sim_pct_60) or pd.isna(cfg_pct_60)) else np.nan)
            delta_120 = (sim_pct_120 - cfg_pct_120
                         if not (pd.isna(sim_pct_120) or pd.isna(cfg_pct_120)) else np.nan)

            # --- Ratios (120 / 60) ---
            ratio_sim = np.nan
            if not pd.isna(sim_pct_60) and sim_pct_60 != 0:
                ratio_sim = sim_pct_120 / sim_pct_60

            ratio_cfg = np.nan
            if not pd.isna(cfg_pct_60) and cfg_pct_60 != 0:
                ratio_cfg = cfg_pct_120 / cfg_pct_60

            # Bias flag: 120-min meetings more overrepresented than 60-min
            bias_120_vs_60 = False
            if not (pd.isna(delta_60) or pd.isna(delta_120)):
                bias_120_vs_60 = delta_120 > delta_60

            # --- Counts by meeting length for this room ---
            lengths = length_by_room.get(room, [])
            lengths = [L for L in lengths if L > 0]
            total_meetings = len(lengths)

            length_counts = {}
            for L in set(lengths):
                c = sum(1 for x in lengths if x == L)
                length_counts[L] = c
                all_lengths.add(L)

            row_dict = {
                'configured_pct_60': cfg_pct_60,
                'simulated_pct_60': sim_pct_60,
                'delta_60': delta_60,
                'configured_pct_120': cfg_pct_120,
                'simulated_pct_120': sim_pct_120,
                'delta_120': delta_120,
                'ratio_120_to_60_config': ratio_cfg,
                'ratio_120_to_60_sim': ratio_sim,
                'bias_120_vs_60': bias_120_vs_60,
                'total_meetings': total_meetings,
            }

            for L, cnt in length_counts.items():
                row_dict[f'count_len_{int(L)}'] = cnt

            summary_rows[room] = row_dict

        summary_df = pd.DataFrame.from_dict(summary_rows, orient='index')
        summary_df.index.name = 'room'

        # Ensure all count_len_<L> columns exist
        for L in sorted(all_lengths):
            col_name = f'count_len_{int(L)}'
            if col_name not in summary_df.columns:
                summary_df[col_name] = 0

        fixed_cols = [c for c in summary_df.columns if not c.startswith('count_len_')]
        count_cols = sorted([c for c in summary_df.columns if c.startswith('count_len_')],
                            key=lambda x: int(x.split('_')[-1]))
        summary_df = summary_df[fixed_cols + count_cols]

        if generate_check_files:
            os.makedirs(self.check_calc_out, exist_ok=True)
            outpath = os.path.join(self.check_calc_out, 'Meeting_Length_Bias_Analysis.xlsx')
            sheet_name = self.config  # one sheet per config model

            # Write/append to Excel, replacing the sheet for this config
            from openpyxl import load_workbook
            if not os.path.exists(outpath):
                with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, sheet_name=sheet_name)
            else:
                with pd.ExcelWriter(outpath, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    summary_df.to_excel(writer, sheet_name=sheet_name)

        return summary_df

    def get_configured_space_parameters(self, generate_check_files: bool = False) -> pd.DataFrame:
        """
        Retrieve configured meeting space parameters from input Excel.
        Args:
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            pd.DataFrame: DataFrame of configured meeting parameters.
        """
        meeting_rooms, offices = self.determine_meeting_or_office()
        space_type_input_df = pd.read_excel(self.input, sheet_name='space_type_input')
        PD = pd.DataFrame()
        cols = list(space_type_input_df.columns)
        for m in meeting_rooms:
            idx = cols.index(m)
            PD[m] = space_type_input_df.iloc[0:10, idx + 1]
        lbls = []
        for l in space_type_input_df[m]:
            try:
                lbls.append(l.split(':')[-1])
            except:
                lbls.append(l)
        PD.insert(0, 'labels', lbls[0:10])
        RS = self.get_allrooms_sptype()
        MTG = pd.DataFrame()
        for m in list(PD.columns)[1::]:
            rooms = RS['rooms'].loc[RS['sptypes'] == m]
            for r in rooms:
                MTG[f'{r}: Configured'] = PD[m]
        sorted_cols = sorted(MTG.columns)
        MTG = MTG[sorted_cols]
        MTG.insert(0, 'labels', PD['labels'])
        if generate_check_files:
            MTG.to_csv(os.path.join(self.check_calc_out, 'Configured_Meeting_Parameters_IND.csv'), index=False)
        return MTG

    def Meetings_Ver(self, offhours_filter=1, generate_check_files: bool = False) -> pd.DataFrame:
        """
        Compare configured vs. simulated meeting parameters.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1).
            generate_check_files (bool): Whether to generate CSV files for verification (default=False).
        Returns:
            pd.DataFrame: Combined DataFrame of configured and simulated meeting parameters.
        """
        outdir = self.check_calc_out
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        Meeting_Params = self.verify_meeting_parameters(offhours_filter)
        MTG = self.get_configured_space_parameters(generate_check_files=generate_check_files)
        ML = self.table_Meetings_Ver(offhours_filter, generate_check_files=generate_check_files)
        for room in Meeting_Params['CountMeetings'].keys():
            days = Meeting_Params['MeetingDays'][room]
            min_occs = np.min(Meeting_Params['CountOccupants'][room])
            max_occs = np.max(Meeting_Params['CountOccupants'][room])
            min_meetings = np.min(Meeting_Params['CountMeetings'][room])
            max_meetings = np.max(Meeting_Params['CountMeetings'][room])
            mlen_30 = ML[room].loc[30]
            mlen_60 = ML[room].loc[60]
            mlen_90 = ML[room].loc[90]
            mlen_120 = ML[room].loc[120]
            MTG[f'{room}: Simulated'] = ['All', ', '.join(days), min_meetings, max_meetings, min_occs, max_occs,
                                         mlen_30, mlen_60, mlen_90, mlen_120]
        sorted_cols = sorted(MTG.columns)
        MTG = MTG[sorted_cols]
        MTG.set_index('labels', inplace=True)
        if generate_check_files:
            MTG.to_csv(os.path.join(outdir, 'MeetingParamsComparison.csv'))
        return MTG

    def verification_normalized(self, offhours_filter=1, cases=['behavior', 'meeting', 'office']) -> pd.DataFrame:
        """
        Compute normalized differences (Simulated - Configured) for specified cases.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (unused but kept for compatibility).
            cases (list): List of cases to process ('behavior', 'meeting', 'office').
        Returns:
            pd.DataFrame: DataFrame of differences for the last processed case.
        """
        for case in cases:
            if case == 'meeting':
                COMB = self.Meetings_Ver(offhours_filter=offhours_filter)
                COMB = COMB.iloc[2::, :]
                fname = 'Meetings_Ratio_Verification.csv'
            elif case == 'office':
                COMB = self.verify_office_breakdown()
                fname = 'Office_Ratio_Verification.csv'
            elif case == 'behavior':
                COMB = self.get_simulated_occ_behavior()
                # COMB = COMB.iloc[5:-4:2, :]  # Uncomment For TYPI, comment line below
                COMB = COMB.iloc[5:-8:2, :]  # Uncomment For non-TYPI, comment line above
                fname = 'Behavior_Ratio_Verification.csv'
            RATIO = pd.DataFrame()
            cols = list(set([c.split(':')[0] for c in COMB.columns]))
            for c in sorted(cols):
                RATIO[c] = COMB[f'{c}: Simulated'] - COMB[f'{c}: Configured']
            COMB.to_csv(os.path.join(self.hm_data_out, fname))
        return RATIO

    def verification_tests(self, tolerance=10.0, cases=['behavior', 'meeting', 'office']) -> pd.DataFrame:
        """
        Compute Pass/Fail results for verification tests per case.
        Args:
            tolerance (float): Tolerance threshold for pass/fail (default=10.0).
            cases (list): List of cases to process ('behavior', 'meeting', 'office').
        Returns:
            pd.DataFrame: Pass/Fail DataFrame for the last processed case.
        """
        for case in cases:
            if case == 'meeting':
                fname = 'Meetings_Ratio_Verification_PF.csv'
                COMB = self.Meetings_Ver()
                PF = pd.DataFrame()
                cols = [c.split(':')[0] for c in COMB.columns]
                COMB.columns = cols
                for c in sorted(list(set(cols))):
                    df = COMB[c]
                    pf = []
                    for l in range(len(COMB[c])):
                        if l in [0, 1]:  # Seasons and Days of week
                            if l == 1:  # Special handling for "Days of week"
                                configured = str(df.iloc[l, 0]).strip()
                                simulated = str(df.iloc[l, 1]).strip()
                                weekdays_str = "Monday, Tuesday, Wednesday, Thursday, Friday"
                                if (configured == "Weekdays" and simulated == weekdays_str) or \
                                   (configured == weekdays_str and simulated == "Weekdays") or \
                                   (configured == simulated):
                                    pf.append(1)
                                else:
                                    pf.append(0)
                            else:  # Seasons or other equality checks
                                if df.iloc[l, 0] == df.iloc[l, 1]:
                                    pf.append(1)
                                else:
                                    pf.append(0)
                        elif l in [2, 4]:  # minimum number of meeting/people per day
                            if df.iloc[l, 0] <= df.iloc[l, 1]:
                                pf.append(1)
                            else:
                                pf.append(0)
                        elif l in [3, 5]:  # maximum number of meeting/people per day
                            if df.iloc[l, 0] >= df.iloc[l, 1]:
                                pf.append(1)
                            else:
                                pf.append(0)
                        elif l in [6, 7, 8, 9]:  # probabilities
                            if np.abs(df.iloc[l, 0] - df.iloc[l, 1]) <= tolerance:
                                pf.append(1)
                            else:
                                pf.append(0)
                    PF[c] = pf
                final_idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
                PF = PF.iloc[final_idx].reset_index(drop=True)
                PF['index'] = list(COMB.index[final_idx])
                PF.set_index('index', inplace=True)
            elif case == 'office':
                fname = 'Office_Ratio_Verification_PF.csv'
                COMB = self.verify_office_breakdown()
                PF = pd.DataFrame()
                cols = [c.split(':')[0] for c in COMB.columns]
                COMB.columns = cols
                for c in sorted(list(set(cols))):
                    df = COMB[c]
                    pf = []
                    for l in range(len(COMB[c])):
                        if np.abs(df.iloc[l, 0] - df.iloc[l, 1]) <= tolerance:
                            pf.append(1)
                        else:
                            pf.append(0)
                    PF[c] = pf
                PF['index'] = list(COMB.index)
                PF.set_index('index', inplace=True)
            elif case == 'behavior':
                fname = 'Behavior_Ratio_Verification_PF.csv'
                COMB = self.get_simulated_occ_behavior()
                idx = [0, 1, 2, 3, 4, 5, 7, 9, 11, 13]
                COMB = COMB.iloc[idx, :]
                PF = pd.DataFrame()
                cols = [c.split(':')[0] for c in COMB.columns]
                COMB.columns = cols
                for c in sorted(list(set(cols))):
                    df = COMB[c]
                    pf = []
                    for l in range(len(COMB[c])):
                        if l == 0:
                            try:
                                if df.iloc[l, 0] == df.iloc[l, 1]:
                                    pf.append(1)
                                else:
                                    if (df.iloc[l, 0] == 'Weekdays') and (df.iloc[l, 1] == 'Monday, Tuesday, Wednesday, Thursday, Friday'):
                                        pf.append(1)
                                    else:
                                        pf.append(0)
                            except:
                                pf.append(0)
                        elif l in [1, 3]:
                            try:
                                def time_seconds(t):
                                    try:
                                        vals = [float(_t) for _t in t.split(':')]
                                        seconds = (vals[0] * 3600) + (vals[1] * 60) + vals[2]
                                    except:
                                        seconds = (t.hour * 3600) + (t.minute * 60) + t.second
                                    return seconds
                                if abs(time_seconds(df.iloc[l, 0]) - time_seconds(df.iloc[l, 1])) <= df.iloc[l + 1, 0] * 60:
                                    pf.append(1)
                                else:
                                    pf.append(0)
                            except:
                                pf.append(0)
                        elif l >= 5:
                            try:
                                if np.abs(float(df.iloc[l, 0]) - float(df.iloc[l, 1])) <= tolerance:
                                    pf.append(1)
                                else:
                                    pf.append(0)
                            except:
                                pf.append(0)
                    PF[c] = pf
                final_idx = [0, 1, 3, 5, 6, 7, 8, 9]
                PF['index'] = COMB.index[final_idx]
                PF.set_index('index', inplace=True)
            final = np.mean(PF, axis=0)
            PF.loc[len(PF)] = final
            PF.index = list(PF.index)[0:-1] + ['Overall Pass/Fail']
            PF.to_csv(os.path.join(self.pf_data_out, fname))
        return PF

    def HM_diff_meetings_ratio_verification(self, offhours_filter=1, excel_export=False):
        """
        Generate a heatmap for the difference (Simulated - Configured) in meeting parameters.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1, unused here).
            excel_export (bool): Whether to export data to Excel/CSV (default=False).
        """
        df = self.verification_normalized(cases=['meeting'])
        df_heat = df.iloc[4::, :]
        df_heat.columns = [d.split('_')[0] for d in df_heat.columns]
        df_heat = df_heat.T
        _labels = [l.replace(' ', '\n') for l in df_heat.columns]
        labels = [l.strip().split('[')[0] for l in _labels]
        if excel_export:
            try:
                df_heat.to_excel(os.path.join(self.hm_data_out, f'HM_Diff_Meetings_Ratio_Verification_Data.xlsx'))
            except Exception:
                df_heat.to_csv(os.path.join(self.hm_data_out, f'HM_Diff_Meetings_Ratio_Verification_Data.csv'))
        plt.rcParams['font.size'] = 25
        fig, ax = plt.subplots(figsize=(21, 11))
        try:
            sns.heatmap(df_heat.astype(float), ax=ax, lw=3, cmap='bwr', vmin=-50, vmax=50, annot=True, annot_kws={"size": 25})
        except Exception:
            pass
        ax.patch.set_edgecolor('black')
        ax.patch.set_linewidth(1)
        plt.xticks(ticks=[x + 0.5 for x in range(len(labels))], labels=labels, rotation=0)
        plt.xlabel('', fontsize=25)
        plt.ylabel('Meeting Rooms', fontsize=25)
        plt.tight_layout()
        plt.savefig(os.path.join(self.hm_out, f'HM_Diff_Meetings_Ratio_Verification.png'))
        plt.close()

    def HM_diff_office_ratio_verification(self, offhours_filter=1, excel_export=False):
        """
        Generate a heatmap for the difference (Simulated - Configured) in office parameters.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1, unused here).
            excel_export (bool): Whether to export data to Excel/CSV (default=False).
        """
        df = self.verification_normalized(cases=['office'])
        df_heat = df.copy().astype(float)
        labels = [l.replace(' ', '\n') for l in df_heat.columns]
        if excel_export:
            try:
                df_heat.to_excel(os.path.join(self.hm_data_out, f'HM_Diff_Office_Ratio_Verification_Data.xlsx'))
            except Exception:
                df_heat.to_csv(os.path.join(self.hm_data_out, f'HM_Diff_Office_Ratio_Verification_Data.csv'))
        plt.rcParams['font.size'] = 25
        fig, ax = plt.subplots(figsize=(21, 11))
        try:
            sns.heatmap(df_heat.astype(float), ax=ax, lw=3, cmap='bwr', vmin=-50, vmax=50, annot=True, annot_kws={"size": 25})
        except Exception:
            pass
        ax.patch.set_edgecolor('black')
        ax.patch.set_linewidth(1)
        plt.xticks(ticks=[x + 0.5 for x in range(len(labels))], labels=labels, rotation=0)
        plt.xlabel('Offices', fontsize=25)
        plt.ylabel('Occupant Types', fontsize=25)
        plt.tight_layout()
        plt.savefig(os.path.join(self.hm_out, f'HM_Diff_Office_Ratio_Verification.png'))
        plt.close()

    def HM_diff_behavior_ratio_verification(self, offhours_filter=1, excel_export=False):
        """
        Generate a heatmap for the difference (Simulated - Configured) in behavior parameters.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1, unused here).
            excel_export (bool): Whether to export data to Excel/CSV (default=False).
        """
        df = self.verification_normalized(cases=['behavior'])
        df_heat = df.T.astype(float)
        _labels = [l.split('-')[-1] for l in df_heat.columns]
        labels = ['percent of\ntime in\n' f'{l.strip()}' for l in _labels]
        if excel_export:
            try:
                df_heat.to_excel(os.path.join(self.hm_data_out, f'HM_Diff_Behavior_Ratio_Verification_Data.xlsx'))
            except Exception:
                df_heat.to_csv(os.path.join(self.hm_data_out, f'HM_Diff_Behavior_Ratio_Verification_Data.csv'))
        plt.rcParams['font.size'] = 25
        fig, ax = plt.subplots(figsize=(21, 11))
        try:
            sns.heatmap(df_heat, ax=ax, lw=3, cmap='bwr', vmin=-50, vmax=50, annot=True, annot_kws={"size": 25})
        except Exception:
            pass
        ax.patch.set_edgecolor('black')
        ax.patch.set_linewidth(1)
        plt.xticks(ticks=[x + 0.5 for x in range(len(labels))], labels=labels, rotation=0)
        plt.xlabel('', fontsize=25)
        plt.ylabel('Occupant Types', fontsize=25)
        plt.tight_layout()
        plt.savefig(os.path.join(self.hm_out, f'HM_Diff_Behavior_Ratio_Verification.png'))
        plt.close()

    def verification_pf_per_config(self, tolerance=10.0, excel_export=False):
        """
        Generate individual Pass/Fail heatmaps for each case (behavior, office, meeting).
        Args:
            tolerance (float): Tolerance threshold for pass/fail (default=10.0).
            excel_export (bool): Whether to export data to Excel/CSV (default=False).
        """
        cases = ['behavior', 'office', 'meeting']
        for case in cases:
            df = self.verification_tests(tolerance=tolerance, cases=[case])
            overall = df.iloc[-1, :]
            df = df.iloc[0:-1, :]
            if case == 'meeting':
                df = df.iloc[1::, :]
                df.columns = [d.split('_')[0] for d in df.columns]
                title = 'Meeting Room Parameters Verification'
                fname = f'PF_Meetings_{self.config}'
                _labels = [l.replace(' ', '\n') for l in df.index]
                labels = [l.strip().split('[')[0] for l in _labels]
                ylabel = 'Meeting Rooms'
                xlabel = ''
            elif case == 'office':
                df = df.T
                title = 'Office Parameters Verification'
                fname = f'PF_Office_{self.config}'
                labels = [l.replace(' ', '\n') for l in df.index]
                ylabel = 'Occupant Types'
                xlabel = 'Offices'
            elif case == 'behavior':
                title = 'Behavior Parameters Verification'
                fname = f'PF_Behavior_{self.config}'
                labels = [l.strip().replace(' ', '\n') for l in df.index]
                _labels = [l.split('-')[-1] for l in labels[3::]]
                __labels = ['percent of\ntime in\n' f'{l.strip()}' for l in _labels]
                labels[3::] = __labels
                ylabel = 'Occupant Types'
                xlabel = ''
            if excel_export:
                try:
                    df.to_excel(os.path.join(self.pf_data_out, f'{fname}_Data.xlsx'))
                except Exception:
                    df.to_csv(os.path.join(self.pf_data_out, f'{fname}_Data.csv'))
            plt.rcParams['font.size'] = 15
            fig, ax = plt.subplots(figsize=(10, 8))
            sns.heatmap(df.T, ax=ax, lw=3, cmap='RdYlGn', cbar=False, vmin=0, vmax=1, annot_kws={"size": 10})
            ax.set_xticks(ticks=[x + 0.5 for x in range(len(labels))], labels=labels, rotation=0)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.title(title)
            plt.tight_layout()
            plt.savefig(os.path.join(self.pf_out, f'{fname}.png'))
            plt.close()

    def run_all_plots(self, offhours_filter=1, tolerance=10.0, excel_export=False, generate_check_files=False):
        """
        Convenience method to run all requested plots for the current configuration.
        Args:
            offhours_filter (int): Whether to apply off-hours filter (default=1).
            tolerance (float): Tolerance threshold for pass/fail (default=10.0).
            excel_export (bool): Whether to export data to Excel/CSV for plots (default=False).
            generate_check_files (bool): Whether to generate additional verification CSV files (default=False).
        """
        # Update method calls to pass generate_check_files if needed
        self.office_breakdown(generate_check_files=generate_check_files)
        self.get_simulated_occ_behavior(generate_check_files=generate_check_files)
        self.sptype_distribution_by_occtype(generate_check_files=generate_check_files)
        self.get_configured_space_parameters(generate_check_files=generate_check_files)
        self.Meetings_Ver(offhours_filter=offhours_filter, generate_check_files=generate_check_files)
        
        self.HM_diff_meetings_ratio_verification(offhours_filter=offhours_filter, excel_export=excel_export)
        self.HM_diff_office_ratio_verification(offhours_filter=offhours_filter, excel_export=excel_export)
        self.HM_diff_behavior_ratio_verification(offhours_filter=offhours_filter, excel_export=excel_export)
        self.verification_pf_per_config(tolerance=tolerance, excel_export=excel_export)

if __name__ == '__main__':
    # Run this for TYPI model - uncomment the following block, and comment the hybrid models block below
    # for config in ['hflm_TYPI']:
    #     ocv = OccVer(config=config, obconfig='fullyear')
    #     generate_check_files = False  # Set to True to generate files in verification_calcs_excel_data folder
    #     ocv.run_all_plots(offhours_filter=1, tolerance=10.0, excel_export=True) # Toggle excel_export to generate verification excel plot data within plot folders


    # Run this for the 3 hybrid models - uncomment the block below, and comment the TYPI block above
    for config in ['hflm_HAHM', 'hflm_HALM', 'hflm_HBLM']:
        ocv = OccVer(config=config, obconfig='fullyear')
        bias_df = ocv.analyze_meeting_length_bias(generate_check_files=True)
        diff_df, underuse_summary = ocv.analyze_behavior_underuse_destinations(generate_check_files=True)
        generate_check_files = False  # Set to True to generate files in verification_calcs_excel_data folder
        ocv.run_all_plots(offhours_filter=1, tolerance=10.0, excel_export=True) # Toggle excel_export to generate verification excel plot data within plot folders