import tkinter as tk
from tkinter import ttk
import pandas as pd
from tkinter import messagebox
import os
import numpy as np
import json
import func_run
import datetime
from helper_functions import Occupancy, SPARQL
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
import warnings
import random
import shutil
import xml.etree.ElementTree as et
from config import config
from templates import (
    behavior_template,
    occ_space_options,
    space_input_template_df,
    get_space_input_template
)

class ResultVisualization:
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent
        self.root.title("Visualization of simulation results")
        
        # Get simulation settings from config (already validated at startup)
        start_month = config.get('sim_start_month')
        start_day = config.get('sim_start_day')
        end_month = config.get('sim_end_month')
        end_day = config.get('sim_end_day')
        timesteps_per_hour = config.get('sim_timesteps_per_hour')
        is_leap_year = config.get('sim_is_leap_year')
        num_days = config.get('sim_num_days')
        
        timestep_minutes = 60 // timesteps_per_hour
        year = 2016 if is_leap_year else 2018
        
        print(f"✓ Using simulation period: {num_days} days")
        print(f"  From {start_month}/{start_day} to {end_month}/{end_day}")
        print(f"  Timestep: {timestep_minutes} minutes")
        
        # Generate date range
        end_minute = 60 - timestep_minutes
        self.time_index = pd.date_range(
            start=f"{year}-{start_month}-{start_day} 0:0",
            end=f"{year}-{end_month}-{end_day} 23:{end_minute:02d}",
            freq=f'{timestep_minutes}min'
        )
        
        # Set up organized folder paths
        self.summaries_path = os.path.join(self.parent.parent.parent.parent.save_path,
                                           config.get('summaries_folder'))
        self.plots_path = os.path.join(self.parent.parent.parent.parent.save_path,
                                       config.get('plots_folder'))
        raw_data_path = os.path.join(self.parent.parent.parent.parent.save_path,
                                     config.get('raw_simulation_data'))
        os.makedirs(self.plots_path, exist_ok=True)
        
        # Read simulation files from raw_simulation_data folder
        sim_file_path = os.path.join(raw_data_path, 'occSim.csv')
        self.df_sim = pd.read_csv(sim_file_path)
        
        # Verify length matches
        if len(self.df_sim) != len(self.time_index):
            messagebox.showerror(
                "Data Mismatch",
                f"Simulation output has {len(self.df_sim)} rows but expected "
                f"{len(self.time_index)} based on user_settings.py.\n\n"
                f"Period: {start_month}/{start_day} to {end_month}/{end_day}\n"
                f"Timestep: {timestep_minutes} minutes\n\n"
                f"This may indicate the simulation failed or used different settings."
            )
            self.root.destroy()
            return
        
        self.df_sim.index = self.time_index
        self.df_sim['Date'] = self.df_sim.index.date
        
        # Calculate simulation period for workdays
        start_date = datetime.date(year, start_month, start_day)
        end_date = datetime.date(year, end_month, end_day)
        start_day_of_year = start_date.timetuple().tm_yday - 1  # 0-indexed
        
        # Load workdays
        date_lst = np.unique(self.time_index.date)
        workdays_df = pd.read_csv(config.get('workdays_file'))
        workdays = workdays_df.iloc[:, 0].to_numpy()
        
        # Extract workdays for simulation period
        end_day_of_year = start_day_of_year + num_days
        if end_day_of_year > len(workdays):
            messagebox.showwarning(
                "Workdays Calendar",
                f"Simulation period exceeds workdays.csv length.\n"
                f"Need {end_day_of_year} days, have {len(workdays)}.\n"
                f"Some days may not be correctly classified as workdays."
            )
            workdays_period = np.concatenate([
                workdays[start_day_of_year:],
                np.zeros(end_day_of_year - len(workdays))
            ])
        else:
            workdays_period = workdays[start_day_of_year:end_day_of_year]
        
        # Filter to workdays
        self.df_sim_workdays = pd.DataFrame()
        for day_index in range(len(date_lst)):
            if day_index < len(workdays_period) and workdays_period[day_index]:
                df_day = self.df_sim[self.df_sim['Date'] == date_lst[day_index]]
                self.df_sim_workdays = pd.concat([self.df_sim_workdays, df_day])
        
        # Room number/Occ number - dynamically parsed to support any simulation configuration
        sim_users_file_path = os.path.join(raw_data_path, 'occSim_by_Occupant.csv')
        
        # Read Room Number & Room ID rows (rows 2-3, right after metadata rows 0-1)
        df_room_temp = pd.read_csv(sim_users_file_path, skiprows=[0, 1], nrows=2, header=None)
        df_room_temp.set_index(0, drop=True, inplace=True)
        self.room_df = df_room_temp
        
        # Read Occupant Number & Occupant ID rows (rows 4-5, right after rows 0-3)
        df_user_temp = pd.read_csv(sim_users_file_path, skiprows=[0, 1, 2, 3], nrows=2, header=None)
        df_user_temp.dropna(axis=1, inplace=True)
        df_user_temp.set_index(0, drop=True, inplace=True)
        self.user_df = df_user_temp
        
        # Simulation results by occ type
        self.df_sim_users = pd.read_csv(sim_users_file_path,
                                        skiprows=[0, 1, 2, 3, 4, 5])
        
        # Verify row count matches
        if len(self.df_sim_users) != len(self.time_index):
            messagebox.showerror(
                "Data Mismatch",
                f"User simulation output has {len(self.df_sim_users)} rows but expected "
                f"{len(self.time_index)} based on user_settings.py.\n\n"
                f"Check that the simulation completed successfully."
            )
            self.root.destroy()
            return
        
        self.df_sim_users.index = self.time_index
        self.df_sim_users['Date'] = self.df_sim_users.index.date
        
        # Filter workdays for user data
        self.df_sim_users_workdays = pd.DataFrame()
        for day_index in range(len(date_lst)):
            if day_index < len(workdays_period) and workdays_period[day_index]:
                df_day = self.df_sim_users[self.df_sim_users['Date'] == date_lst[day_index]]
                self.df_sim_users_workdays = pd.concat([self.df_sim_users_workdays, df_day])
        
        # Read occupant_space_dict.xlsx from summaries folder
        df_occ_space = pd.read_excel(f'{self.summaries_path}/occupant_space_dict.xlsx')
        
        # Update mechanical ids and rooms
        space_input = self.parent.space_input
        mechanical_indexes = []
        for i in range(len(space_input)):
            if space_input['Space Type'].iloc[i] == 'Mechanical':
                mechanical_indexes.append(str(i + 1) + '_')
        
        office_pers_file_path = os.path.join(self.summaries_path,
                                             f'{self.parent.parent.parent.parent.time_now}_Try_Offices.csv')
        office_pers = pd.read_csv(office_pers_file_path, index_col=0)
        self.occupant_types = []
        for col in office_pers.columns[1:]:
            type_str = col.split('- ')[-1].split(' [')[0]
            self.occupant_types.append(type_str)
        
        # Assign occupant numbers to different occupant types
        self.occupant_id_dict = {}
        for i in range(len(self.occupant_types)):
            occupant = self.occupant_types[i]
            df_temp = df_occ_space[df_occ_space['Job type'] == occupant]
            open_temp = []
            private_temp = []
            mechanical_temp = []
            shared_temp = []
            for index in range(len(df_temp)):
                office = df_temp.iloc[index, 2]
                occ_num = str(df_temp.index[index])
                if 'Private' in office:
                    private_temp.append(occ_num)
                elif 'Open' in office:
                    open_temp.append(occ_num)
                elif 'Mechanical' in office:
                    mechanical_temp.append(occ_num)
                elif 'Shared' in office:
                    shared_temp.append(occ_num)
            temp_ids = open_temp + private_temp + mechanical_temp + shared_temp
            self.occupant_id_dict[f'{occupant}: Open office'] = open_temp
            self.occupant_id_dict[f'{occupant}: Private office'] = private_temp
            self.occupant_id_dict[f'{occupant}: Mechanical'] = mechanical_temp
            self.occupant_id_dict[f'{occupant}: Shared office'] = shared_temp
            self.occupant_id_dict[occupant] = temp_ids
        
        # Get room numbers - with defensive parsing for blank/invalid entries
        self.private_numbers = []
        self.open_numbers = []
        self.mechanical_numbers = []
        self.shared_numbers = []
        self.conference_numbers = []
        self.bath_numbers = []
        self.storage_numbers = []
        self.dining_numbers = []
        self.other_numbers = []
        for col in self.room_df.columns:
            item = self.room_df[col].loc['Room ID']
            room_num_raw = self.room_df[col].loc['Room Number']
            
            if pd.isna(item) or pd.isna(room_num_raw):
                continue
            if isinstance(item, str) and item.strip() == '':
                continue
            if isinstance(room_num_raw, str) and room_num_raw.strip() == '':
                continue
            
            try:
                room_num = np.int64(room_num_raw)
            except (ValueError, TypeError):
                continue
            
            if 'Private' in item:
                self.private_numbers.append(room_num)
            elif 'Shared' in item:
                self.shared_numbers.append(room_num)
            elif 'Open' in item:
                self.open_numbers.append(room_num)
            elif 'Mechanical' in item:
                for i in mechanical_indexes:
                    if i in item:
                        self.mechanical_numbers.append(room_num)
            elif 'Conference' in item:
                self.conference_numbers.append(room_num)
            elif 'Bathroom' in item:
                self.bath_numbers.append(room_num)
            elif 'Storage' in item:
                self.storage_numbers.append(room_num)
            elif 'Dining' in item:
                self.dining_numbers.append(room_num)
            else:
                self.other_numbers.append(room_num)
        
        self.create_widgets()
        
        matplotlib.rcParams['figure.figsize'] = [18, 9]
        self.fig, self.ax = plt.subplots()
        cmap = plt.get_cmap('viridis')
        num_colors = len(self.occupant_types)
        colors_ = [matplotlib.colors.rgb2hex(cmap(i / (num_colors - 1))) for i in range(num_colors)]
        self.colors = {}
        for col in range(len(self.occupant_types)):
            col_name = self.occupant_types[col]
            self.colors[col_name] = colors_[col]
        
        # Automatically generate ALL plots (not just user-clicked ones)
        print("Generating all plots...")
        self.whole_bldg()
        self.open_office()
        self.private_office()
        self.shared_office()
        self.mechanical_room()
        self.conference_rooms()
        self.dining_rooms()
        self.bathroom()
        self.storage_rooms()
        print(f"✓ All plots saved to: {self.plots_path}")

    def create_widgets(self):
        btn_whole_bldg = tk.Button(self.root, text="Whole building", command=self.whole_bldg)
        btn_whole_bldg.grid(row=0, column=0, padx=5, pady=5)
        btn_open = tk.Button(self.root, text='Open Offices', command=self.open_office)
        btn_open.grid(row=0, column=1, padx=5, pady=5)
        btn_private = tk.Button(self.root, text='Private Offices', command=self.private_office)
        btn_private.grid(row=0, column=2, padx=5, pady=5)
        btn_mechanical = tk.Button(self.root, text='Mechanical Rooms', command=self.mechanical_room)
        btn_mechanical.grid(row=0, column=3, padx=5, pady=5)
        btn_shared = tk.Button(self.root, text='Shared Offices', command=self.shared_office)
        btn_shared.grid(row=0, column=4, padx=5, pady=5)
        btn_conference = tk.Button(self.root, text='Conference rooms', command=self.conference_rooms)
        btn_conference.grid(row=1, column=0, padx=5, pady=5)
        btn_dining = tk.Button(self.root, text='Dining rooms', command=self.dining_rooms)
        btn_dining.grid(row=1, column=1, padx=5, pady=5)
        btn_bathroom = tk.Button(self.root, text='Bathrooms', command=self.bathroom)
        btn_bathroom.grid(row=1, column=2, padx=5, pady=5)
        btn_storage = tk.Button(self.root, text='Storage rooms', command=self.storage_rooms)
        btn_storage.grid(row=1, column=3, padx=5, pady=5)
        btn_return = tk.Button(self.root, text='Finish and close!', command=self.new_app_close)
        btn_return.grid(row=1, column=4, padx=5, pady=5)

    def new_app_close(self):
        self.parent.root.destroy()
        self.parent.parent.root.destroy()
        self.parent.parent.parent.root.destroy()
        self.parent.parent.parent.parent.root.destroy()

    def whole_bldg(self):
        occ_whole_building = self.df_sim_workdays[['Time', 'Date', 'Whole building']]
        occ_whole_building['Normalized'] = (occ_whole_building['Whole building'] /
                                            occ_whole_building['Whole building'].max()) * 100
        occ_whole_building['HH:MM'] = occ_whole_building.index.time
        df_daily = pd.DataFrame(index=['max', 'min', 'mean'])
        for t in np.unique(occ_whole_building.index.time):
            df_temp = occ_whole_building[occ_whole_building['HH:MM'] == t]
            max_occ = df_temp['Normalized'].max()
            min_occ = df_temp['Normalized'].min()
            avg_occ = df_temp['Normalized'].mean()
            df_daily[f'{t}'] = [max_occ, min_occ, avg_occ]
        df_plot = df_daily.T
        df_plot.index = df_plot.index.astype('datetime64[ns]')
        self.ax.cla()
        sns.lineplot(ax=self.ax, data=df_plot, palette='mako', linewidth=3)
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Presence percentage - Whole building (%)', fontsize=16, labelpad=20)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'whole_bldg.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def _generic_stackplot(self, numbers_list, title, filename, use_type_specific_rooms=True):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            if use_type_specific_rooms:
                df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[test_id]]
            else:
                df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[f'{test_id}: {title}']]
            bool_df = df_cleaning.isin(numbers_list)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title(title, fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, filename))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def open_office(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[f'{test_id}: Open office']]
            bool_df = df_cleaning.isin(self.open_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Open office', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'open_office.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def private_office(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[f'{test_id}: Private office']]
            bool_df = df_cleaning.isin(self.private_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Private office', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'private_office.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def shared_office(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[f'{test_id}: Shared office']]
            bool_df = df_cleaning.isin(self.shared_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Shared office', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'shared_office.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def mechanical_room(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[f'{test_id}: Mechanical']]
            bool_df = df_cleaning.isin(self.mechanical_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Mechanical room', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'mechanical.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def conference_rooms(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[test_id]]
            bool_df = df_cleaning.isin(self.conference_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Conference room', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'conference.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def dining_rooms(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[test_id]]
            bool_df = df_cleaning.isin(self.dining_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Dining room', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'dining.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def bathroom(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[test_id]]
            bool_df = df_cleaning.isin(self.bath_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Bathroom', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'bathroom.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

    def storage_rooms(self):
        df_stack_mean = pd.DataFrame()
        for test_id in self.occupant_types:
            df_cleaning = self.df_sim_users_workdays[self.occupant_id_dict[test_id]]
            bool_df = df_cleaning.isin(self.storage_numbers)
            df_cleaning = df_cleaning.where(bool_df)
            df_cleaning['Count'] = df_cleaning[df_cleaning > 0].count(axis=1)
            df_cleaning['Time'] = self.df_sim_users_workdays['Time']
            df_cleaning['HH:MM'] = self.df_sim_users_workdays.index.time
            df_daily = pd.DataFrame()
            for t in np.unique(self.time_index.time):
                df_hour = df_cleaning[df_cleaning['HH:MM'] == t]
                df_daily[f'{t}'] = df_hour['Count'].reset_index(drop=True)
            df_plot_day = df_daily.T
            df_plot_day.index = df_plot_day.index.astype('datetime64[ns]')
            df_stack_mean[test_id] = df_plot_day.mean(axis=1)
        totals = df_stack_mean.sum()
        sorted_totals = totals.sort_values()
        sorted_columns = sorted_totals.index
        self.ax.cla()
        self.ax.stackplot(df_stack_mean.index,
                          [df_stack_mean[col] for col in sorted_columns],
                          labels=sorted_columns,
                          colors=[self.colors[col] for col in sorted_columns])
        hours = matplotlib.dates.HourLocator(interval=2)
        h_fmt = matplotlib.dates.DateFormatter('%H:%M')
        self.ax.xaxis.set_major_locator(hours)
        self.ax.xaxis.set_major_formatter(h_fmt)
        self.ax.set_ylabel('Occupancy count (average)', fontsize=16, labelpad=20)
        self.ax.set_title('Storage room', fontsize=16)
        self.ax.tick_params(axis='both', which='major', labelsize=16)
        self.ax.legend(fontsize=16)
        self.ax.grid(which='major')
        self.fig.tight_layout()
        self.fig.savefig(os.path.join(self.plots_path, 'storage.png'))
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.draw()
        canvas.get_tk_widget().grid(row=2, columnspan=5, padx=10, pady=10)

class RoomSetting:
    def __init__(self, root, parent):
        self.root = root
        self.root.title("Room settings")
        self.parent = parent
        
        # Set up summaries_path once, used throughout this class
        self.summaries_path = os.path.join(self.parent.parent.parent.save_path,
                                           config.get('summaries_folder'))
        os.makedirs(self.summaries_path, exist_ok=True)
        
        lbl_space = tk.Label(self.root, text='Room settings')
        lbl_space.grid(row=0, column=0, padx=10, pady=10)
        self.button_new = tk.Button(self.root, text='Confirm and RUN simulation!', command=self.run_simulation)
        self.button_new.grid(row=0, column=2, padx=10, pady=10)
        self.button_return = tk.Button(self.root, text='Return previous', command=self.return_previous)
        self.button_return.grid(row=0, column=3, padx=10, pady=10)
        self.frame_labels = ['Private Office',
                             'Open Office',
                             'Conference room']
        self.room_labels = ['Private Office',
                            'Open Office',
                            'Shared Office',
                            'Mechanical Room',
                            'Conference room']
        df_temp = pd.read_csv(
            f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Try_Occupancy types.csv'
        )

        self.occupant_types = df_temp['Name'].tolist()
        self.pers = []
        var = 0
        while var <= 100:
            var_str = "{}".format(var)
            self.pers.append(var_str)
            var += 5
        self.settings = {}
        self.saved_settings = {}
        self.custom_frames = {}
        self.frames = {}
        self.radio_vars = {}
        for i in range(1, 4):
            frame = ttk.Frame(self.root, padding="10", relief=tk.RAISED)
            frame.grid(row=1, column=i - 1, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
            self.frames[f'frame{i}'] = frame
            self.radio_vars[f'frame{i}'] = tk.StringVar(value="Default")
            self.create_main_frame_content(frame, i)

    def create_main_frame_content(self, frame, frame_number):
        label = ttk.Label(frame, text=f"Settings: {self.frame_labels[frame_number - 1]}")
        label.grid(row=0, column=0, padx=5, pady=5)
        default_rb = ttk.Radiobutton(frame, text="Default",
                                     variable=self.radio_vars[f'frame{frame_number}'],
                                     value="Default",
                                     command=lambda: self.toggle_customization(frame_number))
        default_rb.grid(row=1, column=0, padx=5, pady=5)
        customize_rb = ttk.Radiobutton(frame, text="Customize",
                                       variable=self.radio_vars[f'frame{frame_number}'],
                                       value="Customize",
                                       command=lambda: self.toggle_customization(frame_number))
        customize_rb.grid(row=2, column=0, padx=5, pady=5)
        custom_frame = ttk.Frame(frame, padding="10")
        custom_frame.grid(row=3, column=0, padx=5, pady=5,
                          sticky=(tk.W, tk.E, tk.N, tk.S))
        custom_frame.grid_forget()
        self.custom_frames[f'frame{frame_number}'] = custom_frame
        self.create_customization_content(custom_frame, frame_number)

    def create_customization_content(self, frame, frame_number):
        entry_labels = ['minimum number of meeting per day',
                        'maximum number of meeting per day',
                        'minimum number of people per meeting',
                        'maximum number of people per meeting',
                        'probability of 30-min meetings [%]',
                        'probability of 60-min meetings [%]',
                        'probability of 90-min meetings [%]',
                        'probability of 120-min meetings [%]']
        days_options = ['Weekdays', 'Monday - Thursday', 'Tuesday - Thursday',
                        'Monday - Wednesday', 'Customize']
        if frame_number <= 2:
            label1 = ttk.Label(frame, text="Percentages")
            label1.grid(row=0, column=0, padx=5, pady=5)
            combo1 = ttk.Combobox(frame, values=self.pers, state='readonly', width=10)
            combo1.grid(row=0, column=1, padx=5, pady=5)
            combo1.set(10)
            self.settings[f'{self.frame_labels[frame_number - 1]}: percentages'] = combo1
            for i in range(len(self.occupant_types)):
                label = ttk.Label(frame, text=f"occupant percentage - {self.occupant_types[i]} [%]")
                label.grid(row=i + 1, column=0, padx=5, pady=5)
                combo = ttk.Combobox(frame, values=self.pers, state='readonly', width=10)
                combo.grid(row=i + 1, column=1, padx=5, pady=5)
                combo.set(0)
                self.settings[
                    f'{self.frame_labels[frame_number - 1]}: occupant percentage - {self.occupant_types[i]} [%]'] = combo
        else:
            label1 = ttk.Label(frame, text="Percentages")
            label1.grid(row=0, column=0, padx=5, pady=5)
            combo1 = ttk.Combobox(frame, values=['10', '20', '30', '40', '50', '60', '70', '80', '90', '100'],
                                  state='readonly', width=10)
            combo1.grid(row=0, column=1, padx=5, pady=5)
            combo1.set(10)
            self.settings[f'{self.frame_labels[frame_number - 1]}: percentages'] = combo1
            for j in range(1, len(entry_labels) + 2):
                if j == 1:
                    entry_label = 'Days of week'
                    lbl_entry = tk.Label(frame, text=entry_label)
                    lbl_entry.grid(row=1, column=0, padx=5, pady=5)
                    entry_text = tk.StringVar()
                    entry_text.set('Weekdays')
                    entry1 = ttk.Combobox(frame, width=20, state='readonly',
                                          textvariable=entry_text,
                                          values=days_options)
                    entry1.grid(row=1, column=1, padx=5, pady=5)
                    entry1.bind("<<ComboboxSelected>>",
                                lambda event, index=frame_number: self.on_combobox_selected(event, index))
                    custom_text = tk.StringVar()
                    custom_entry = tk.Entry(frame, textvariable=custom_text, width=20)
                    custom_entry.grid(row=2, column=1, padx=5, pady=5)
                    custom_entry.grid_remove()
                    self.frames[f'frame{frame_number}'].entry1 = entry1
                    self.frames[f'frame{frame_number}'].custom_entry = custom_entry
                    self.settings[f'{self.frame_labels[frame_number - 1]}: days of week'] = entry1
                    self.settings[
                        f'{self.frame_labels[frame_number - 1]}: customize days of week'] = custom_entry
                else:
                    entry_label = entry_labels[j - 2]
                    lbl_entry = tk.Label(frame, text=entry_label)
                    lbl_entry.grid(row=j + 1, column=0, padx=5, pady=5)
                    if j <= 5:
                        entry_text = tk.StringVar()
                        entry_text.set('0')
                        entry = tk.Entry(frame, textvariable=entry_text, width=20)
                        entry.grid(row=j + 1, column=1, padx=5, pady=5)
                    else:
                        entry_text = tk.StringVar()
                        entry = ttk.Combobox(frame, width=20, state='readonly',
                                             textvariable=entry_text,
                                             values=self.pers)
                        entry.grid(row=j + 1, column=1, padx=5, pady=5)
                        entry.set('0')
                    self.settings[f'{self.frame_labels[frame_number - 1]}: {entry_label}'] = entry

    def on_combobox_selected(self, event, index):
        selected_option = self.frames[f'frame{index}'].entry1.get()
        if selected_option == "Customize":
            self.frames[f'frame{index}'].custom_entry.grid()
        else:
            self.frames[f'frame{index}'].custom_entry.grid_remove()

    def toggle_customization(self, frame_number):
        if self.radio_vars[f'frame{frame_number}'].get() == "Customize":
            self.custom_frames[f'frame{frame_number}'].grid(row=3, column=0, padx=5, pady=5,
                                                            sticky=(tk.W, tk.E, tk.N, tk.S))
        else:
            self.custom_frames[f'frame{frame_number}'].grid_forget()

    def return_previous(self):
        self.root.destroy()
        self.parent.root.deiconify()

    def run_simulation(self):
        for frame_number, radio_var in self.radio_vars.items():
            if radio_var.get() == 'Customize':
                j = frame_number[-1]
                for key in self.settings.keys():
                    if self.frame_labels[int(j) - 1] in key:
                        self.saved_settings[key] = self.settings[key].get()
        
        df_occ = pd.read_csv(
            f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Try_Occupancy types.csv')
        df_office = pd.read_csv(
            f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Try_Offices.csv')
        df_meeting = pd.read_csv(
            f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Try_Meeting rooms.csv')
        
                
        try:
            occ_space_other_options = pd.read_csv(
                f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Added Occupancy types.csv')
        except Exception:
            occ_space_other_options = occ_space_options.copy()
        
        query = """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX s223: <http://data.ashrae.org/standard223#>
                    SELECT ?number ?roomname ?area (SUM(?power) AS ?room_power) #
                    WHERE  
                      {
                      ?light a s223:Luminaire.
                      ?light s223:hasPhysicalLocation ?room.
                      ?room rdfs:label ?roomname.
                      ?light s223:hasProperty ?lightproperty.
                      ?room s223:hasProperty ?roomnumber.
                      ?roomnumber a s223:Property.
                      ?roomnumber s223:hasValue ?number.
                      ?light s223:hasProperty ?lightproperty.
                      ?roomproperty a s223:QuantifiableProperty.
                      ?lightproperty a s223:QuantifiableProperty.
                      ?lightproperty s223:hasValue ?power.
                      ?room s223:hasProperty ?roomproperty.
                      ?roomproperty s223:hasValue ?area.
                        }
                    GROUP BY  ?number ?roomname ?area
                    """
        PD = SPARQL().run_query(query)
        idx = []
        for i in range(len(PD['?roomname'])):
            if PD['?roomname'].iloc[i].toPython() == 'Hallway' or PD['?roomname'].iloc[i].toPython() == 'Stairwell':
                idx.append(i)
        PD = PD.drop(idx)
        PD.reset_index(inplace=True, drop=True)
        idx_private = []
        idx_open = []
        idx_conference = []
        idx_others = []
        for i in range(len(PD['?roomname'])):
            room = PD['?roomname'].iloc[i].toPython()
            if room == 'Private Office':
                idx_private.append(i)
            elif room == 'Open Office':
                idx_open.append(i)
            elif room == 'Conference room':
                idx_conference.append(i)
            else:
                idx_others.append(i)
        PD_private = PD.loc[idx_private]
        PD_open = PD.loc[idx_open]
        PD_conference = PD.loc[idx_conference]
        PD_others = PD.loc[idx_others]
        id_shared = random.sample(idx_private, 3)
        for i in id_shared:
            PD_private.loc[i, '?roomname'] = 'Shared Office'
        PD_new = pd.concat([PD_private, PD_open, PD_conference, PD_others])
        PD_new = PD_new.sample(frac=1).reset_index(drop=True)
        PD_new.to_csv(f'{self.summaries_path}/{self.parent.parent.parent.time_now}_Room_Dict.csv')
        
        private_office = []
        open_office = []
        conference = []
        for i in range(len(PD_new['?roomname'])):
            try:
                room = PD_new['?roomname'].iloc[i].toPython()
            except Exception:
                room = PD_new['?roomname'].iloc[i]
            if 'Private' in room:
                private_office.append(PD_new['?number'].iloc[i].toPython())
            elif 'Open' in room:
                open_office.append(PD_new['?number'].iloc[i].toPython())
            elif 'Conference' in room:
                conference.append(PD_new['?number'].iloc[i].toPython())
        room_numbers = {'Private Office': private_office,
                        'Open Office': open_office,
                        'Conference room': conference}
        room_from = list(np.unique([x.split(': ')[0] for x in list(self.saved_settings.keys())]))
        
        if len(room_from) == 0:
            df_meeting_new = df_meeting.copy()
            df_office_new = df_office.copy()
        else:
            df_p_office_ = pd.DataFrame()
            df_o_office_ = pd.DataFrame()
            inserted_df = pd.DataFrame()
            for office in room_from:
                if office == 'Conference room':
                    room_lst = room_numbers[office]
                    settings = []
                    for key in self.saved_settings.keys():
                        if f'{office}: ' in key:
                            settings.append(self.saved_settings[key])
                    per = settings[0]
                    if int(len(room_lst) * int(per) / 100) == 0:
                        rand_num = 1
                    else:
                        rand_num = int(len(room_lst) * int(per) / 100)
                    rand_room = random.sample(room_lst, rand_num)
                    if settings[1] == 'Customize':
                        days = settings[2]
                    elif settings[1] == 'Weekdays':
                        days = 'Monday, Tuesday, Wednesday, Thursday, Friday'
                    elif settings[1] == 'Monday - Thursday':
                        days = 'Monday, Tuesday, Wednesday, Thursday'
                    elif settings[1] == 'Tuesday - Thursday':
                        days = 'Tuesday, Wednesday, Thursday'
                    elif settings[1] == 'Monday - Wednesday':
                        days = 'Monday, Tuesday, Wednesday'
                    else:
                        days = 'Monday, Tuesday, Wednesday, Thursday, Friday'
                    other_settings = settings[-8:]
                    for room_index in range(len(rand_room)):
                        room = rand_room[room_index]
                        insert_row = ['Conference Room ' + room, days] + other_settings
                        inserted_df[room_index] = insert_row
                    inserted_df = inserted_df.T
                    inserted_df.columns = df_meeting.columns
                elif office == 'Private Office':
                    room_lst = room_numbers[office]
                    settings = []
                    for key in self.saved_settings.keys():
                        if f'{office}: ' in key:
                            settings.append(self.saved_settings[key])
                    per = settings[0]
                    rand_room = random.sample(room_lst, int(len(room_lst) * int(per) / 100))
                    for room_index in range(len(rand_room)):
                        room = rand_room[room_index]
                        inserted_row = ['Private office ' + room, '1'] + settings[-len(self.occupant_types):]
                        df_p_office_[room_index] = inserted_row
                    df_p_office_ = df_p_office_.T
                    df_p_office_.columns = df_office.columns
                elif office == 'Open Office':
                    room_lst = room_numbers[office]
                    settings = []
                    for key in self.saved_settings.keys():
                        if f'{office}: ' in key:
                            settings.append(self.saved_settings[key])
                    per = settings[0]
                    rand_room = random.sample(room_lst, int(len(room_lst) * int(per) / 100))
                    for room_index in range(len(rand_room)):
                        room = rand_room[room_index]
                        inserted_row = ['Open Office ' + room, '1'] + settings[-len(self.occupant_types):]
                        df_o_office_[room_index] = inserted_row
                    df_o_office_ = df_o_office_.T
                    df_o_office_.columns = df_office.columns
            df_office_new = pd.concat([df_office, df_p_office_, df_o_office_]).reset_index(drop=True)
            df_meeting_new = pd.concat([df_meeting, inserted_df]).reset_index(drop=True)
        
        df_meeting_new.to_csv(f'{self.summaries_path}/'
                              f'{self.parent.parent.parent.time_now}_new_meetings.csv',
                              index=False)
        df_office_new.to_csv(f'{self.summaries_path}/'
                             f'{self.parent.parent.parent.time_now}_new_office.csv',
                             index=False)
        df_meeting_new_new = pd.read_csv(f'{self.summaries_path}/'
                                         f'{self.parent.parent.parent.time_now}_new_meetings.csv')
        df_office_new_new = pd.read_csv(f'{self.summaries_path}/'
                                        f'{self.parent.parent.parent.time_now}_new_office.csv')
        office_names = df_office_new_new.iloc[:, 0].tolist()
        meeting_rooms = df_meeting_new_new.iloc[:, 0].tolist()
        
        df_office_inputs = pd.DataFrame()
        for office in office_names:
            values = df_office_new_new[df_office_new_new.iloc[:, 0] == office].iloc[:, 1:]
            column_names = values.columns.tolist()
            index_column = []
            for i in range(len(column_names)):
                text = 'Office: ' + column_names[i]
                index_column.append(text)
            df_temp = pd.DataFrame({office: index_column,
                                    'Default Value': values.iloc[0, :]})
            df_office_inputs = pd.concat([df_office_inputs, df_temp], axis=1)
        
        df_meeting_inputs = pd.DataFrame()
        for meeting in meeting_rooms:
            values = df_meeting_new_new[df_meeting_new_new.iloc[:, 0] == meeting].iloc[:, 1:]
            values.insert(loc=0, column='Seasons', value='Summer, Winter, Spring, Fall')
            column_names = values.columns.tolist()
            index_column = []
            for i in range(len(column_names)):
                text = meeting + ': ' + column_names[i]
                index_column.append(text)
            index_column[:2] = column_names[:2]
            df_temp = pd.DataFrame({meeting: index_column,
                                    'Default Value': values.iloc[0, :]})
            df_temp.dropna(how='any', axis=0)
            df_meeting_inputs = pd.concat([df_meeting_inputs, df_temp], axis=1)
        
        input_filename = f'{self.summaries_path}/{self.parent.parent.parent.time_now}_temp_input.xlsx'
        
        df_ex = pd.DataFrame()
        df_ex.to_excel(input_filename)
        writer = pd.ExcelWriter(
            input_filename,
            engine='openpyxl', mode='a', if_sheet_exists='overlay')
        df_office_inputs = df_office_inputs.T.reset_index().T
        df_office_inputs.to_excel(writer, sheet_name='space_type_input', index=False, header=False,
                                  startcol=0, startrow=0)
        df_meeting_inputs = df_meeting_inputs.T.reset_index().T
        df_meeting_inputs.to_excel(writer, sheet_name='space_type_input', index=False, header=False,
                                   startcol=len(df_office_inputs.columns),
                                   startrow=0)
        writer.close()
        
        occ_types = df_occ['Name'].tolist()
        for idx in range(len(occ_types)):
            occ_type = occ_types[idx]
            occ_input = df_occ[df_occ['Name'] == occ_type].iloc[:, 1:]
            occ_input.insert(loc=0, column='Season', value='All')
            occ_input.insert(loc=1, column='Days', value=behavior_template.iloc[1, 1])
            try:
                add_values = occ_space_options[occ_type]
            except Exception:
                add_values = occ_space_other_options[occ_type][1:].astype('float64')
            occ_input_final = pd.concat([occ_input.iloc[0, :6], add_values, occ_input.iloc[0, 6:]])
            column_names = behavior_template.iloc[:, 0][:-4]
            index_column = []
            for i in range(len(column_names)):
                text = occ_type + ': ' + column_names[i]
                index_column.append(text)
            index_column[:2] = column_names[:2]
            st_col_names = behavior_template.iloc[:, 0][-4:].reset_index(drop=True)
            added_cols = []
            for i in range(len(st_col_names)):
                text = occ_type + ': ' + st_col_names[i]
                added_cols.append(text)
            dif_ = len(occ_input_final) - len(index_column)
            index_column += added_cols * int(dif_ / 4)
            df_temp = pd.DataFrame({occ_type: index_column,
                                    'Values': occ_input_final})
            df_temp.dropna(how='any', axis=0, inplace=True)
            df_temp = df_temp.T.reset_index().T
            writer = pd.ExcelWriter(
                input_filename,
                engine='openpyxl', mode='a', if_sheet_exists='overlay',
                datetime_format='HH:MM')
            df_temp.to_excel(writer, sheet_name='behavior_input', index=False, header=False,
                             startrow=0, startcol=2 * idx)
            writer.close()
        
        space_input_template = get_space_input_template()
        for i in range(len(PD_new)):
            try:
                space_input_template.loc[i, 'Room/Enclosure'] = PD_new['?roomname'][i].toPython()
            except Exception:
                space_input_template.loc[i, 'Room/Enclosure'] = PD_new['?roomname'][i]
        for i in range(len(space_input_template['Room/Enclosure'])):
            if space_input_template.loc[i, 'Room/Enclosure'] == 'Private Office':
                space_input_template.loc[i, 'Space Type'] = 'Private Office'
                space_input_template.loc[i, 'Number of occupants'] = 1
                space_input_template.loc[i, 'Occupant density (m^2/person)'] = 1
                space_input_template.loc[i, 'Area (m^2)'] = 1
            elif space_input_template.loc[i, 'Room/Enclosure'] == 'Open Office':
                space_input_template.loc[i, 'Space Type'] = 'Open Office'
                space_input_template.loc[i, 'Number of occupants'] = round(
                    PD_new['?area'].iloc[i].toPython() / 9)
                space_input_template.loc[i, 'Occupant density (m^2/person)'] = 9
                space_input_template.loc[i, 'Area (m^2)'] = PD_new['?area'].iloc[i].toPython()
            elif space_input_template.loc[i, 'Room/Enclosure'] == 'Shared Office':
                space_input_template.loc[i, 'Space Type'] = 'Shared Office'
                space_input_template.loc[i, 'Number of occupants'] = 2
                space_input_template.loc[i, 'Occupant density (m^2/person)'] = 1
                space_input_template.loc[i, 'Area (m^2)'] = 2
            elif space_input_template.loc[i, 'Room/Enclosure'] == 'Mechanical Room':
                space_input_template.loc[i, 'Space Type'] = 'Mechanical'
                space_input_template.loc[i, 'Number of occupants'] = 1
                space_input_template.loc[i, 'Occupant density (m^2/person)'] = 1
                space_input_template.loc[i, 'Area (m^2)'] = 1
            elif space_input_template.loc[i, 'Room/Enclosure'] == 'Conference room':
                space_input_template.loc[i, 'Space Type'] = 'Conference Room'
            else:
                space_input_template.loc[i, 'Space Type'] = 'Other'
            space_input_template.loc[i, 'Qty'] = 1
        
        id_mechanical_new = []
        for i in range(len(space_input_template)):
            if space_input_template.loc[i, 'Space Type'] == 'Mechanical':
                id_mechanical_new.append(i)
        id_mech_rand = random.sample(id_mechanical_new, 3)
        for i in id_mech_rand:
            space_input_template.loc[i, 'Space Type'] = 'Other'
            space_input_template.loc[i, 'Area (m^2)'] = np.nan
            space_input_template.loc[i, 'Occupant density (m^2/person)'] = np.nan
            space_input_template.loc[i, 'Number of occupants'] = np.nan
        self.space_input = space_input_template
        
        writer = pd.ExcelWriter(
            input_filename,
            engine='openpyxl', mode='a', if_sheet_exists="replace")
        space_input_template.to_excel(writer, sheet_name='space_input', index=False)
        writer.close()
        
        # Create raw data and plots folders (summaries already created in __init__)
        raw_data_path = os.path.join(self.parent.parent.parent.save_path, config.get('raw_simulation_data'))
        os.makedirs(raw_data_path, exist_ok=True)
        
        output_xml_name = config.get('output_xml')
        simulation_output_string = os.path.join(raw_data_path, 'occSim')
        
        func_run.generate_occupant_behavior_simulation_xml(input_filename, output_xml_name)
        func_run.run_occSim_FMU(output_xml_name, simulation_output_string)
        
        json_str = json.dumps(func_run.timer.__dict__)
        with open(func_run.direc_run_OOS + "timer_output.json", "w") as output_file:
            output_file.write(json_str)
        
        occ_space_dict_filename = config.get('occupant_space_dict')
        shutil.copy2(occ_space_dict_filename, self.summaries_path)
        shutil.copy2(output_xml_name, self.summaries_path)
        
        new_input_root = tk.Toplevel(self.root)
        ResultVisualization(new_input_root, self)
        self.root.withdraw()


class SpaceInputsMeetings:
    def __init__(self, root, parent):
        self.root = root
        self.root.title('Custom Meeting Rooms')
        self.parent = parent

        self.frame_entries = []
        self.frame_custom_entries = []
        self.frame_names = ['Conference Room',
                            'Food Prep',
                            'Classroom',
                            'Collaboration']

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        width = min(1600, sw)
        height = min(900, sh)
        self.root.geometry(f"{width}x{height}")

        self.create_widgets()
        self.create_tooltip()

    def create_widgets(self):
        lbl_space = tk.Label(self.root, text='Meeting rooms and Others')
        lbl_space.pack(side=tk.TOP, anchor='w', padx=10, pady=5)

        top_btn_frame = tk.Frame(self.root)
        top_btn_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        self.button_new = tk.Button(top_btn_frame,
                                    text='Save and continue: Final Touch!',
                                    command=self.go_office_setting)
        self.button_new.pack(side=tk.RIGHT, padx=5)

        self.button_return = tk.Button(top_btn_frame,
                                       text='Return previous',
                                       command=self.return_previous)
        self.button_return.pack(side=tk.RIGHT, padx=5)

        self.lbl_status = tk.Label(self.root, text='', fg='green')
        self.lbl_status.pack(pady=5)

        container = tk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, height=600)
        h_scrollbar = tk.Scrollbar(container, orient="horizontal",
                                   command=canvas.xview)

        scroll_frame = tk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        def _on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

        num_frames = 4

        self.entry_labels = [
            'minimum number of meeting per day',
            'maximum number of meeting per day',
            'minimum number of people per meeting',
            'maximum number of people per meeting',
            'probability of 30-min meetings [%]',
            'probability of 60-min meetings [%]',
            'probability of 90-min meetings [%]',
            'probability of 120-min meetings [%]'
        ]

        days_options = ['Weekdays', 'Monday - Thursday', 'Tuesday - Thursday',
                        'Monday - Wednesday', 'Customize']

        pers = [str(v) for v in range(0, 101, 5)]

        self.frames = []
        for i in range(1, num_frames + 1):
            frame_name = self.frame_names[i - 1]
            frame = ttk.LabelFrame(scroll_frame, text=frame_name)
            frame.grid(row=0, column=i - 1, padx=10, pady=10, sticky="n")
            self.frames.append(frame)

            page_data = {}
            page_customize_data = {}

            entry_label = 'Days of week'
            lbl_entry = tk.Label(frame, text=entry_label)
            lbl_entry.grid(row=0, column=0, padx=5, pady=5)

            entry_text = tk.StringVar()
            entry_text.set('Weekdays')
            entry1 = ttk.Combobox(frame, width=20, state='readonly',
                                  textvariable=entry_text,
                                  values=days_options)
            entry1.grid(row=0, column=1, padx=5, pady=5)
            entry1.bind("<<ComboboxSelected>>",
                        lambda event, index=i-1: self.on_combobox_selected(event, index))

            custom_text = tk.StringVar()
            custom_entry = tk.Entry(frame, textvariable=custom_text, width=20)
            custom_entry.grid(row=1, column=1, padx=5, pady=5)
            custom_entry.grid_remove()

            custom_entry.bind("<Enter>", lambda event, index=i-1: self.show_tooltip(event, index))
            custom_entry.bind("<Leave>", self.hide_tooltip)

            self.frames[i-1].entry1 = entry1
            self.frames[i-1].custom_entry = custom_entry

            page_data[entry_label] = entry_text
            page_customize_data[entry_label] = custom_text

            for j, label in enumerate(self.entry_labels, start=1):
                lbl_entry = tk.Label(frame, text=label)
                lbl_entry.grid(row=j + 1, column=0, padx=5, pady=5)

                if j <= 4:
                    entry_text2 = tk.StringVar()
                    if frame_name == 'Conference Room':
                        if 'minimum' in label and 'meeting' in label:
                            entry_text2.set('0')
                        elif 'maximum' in label and 'meeting' in label:
                            entry_text2.set('5')
                        elif 'minimum' in label and 'people' in label:
                            entry_text2.set('4')
                        elif 'maximum' in label and 'people' in label:
                            entry_text2.set('12')
                    elif frame_name == 'Food Prep':
                        if 'minimum' in label and 'meeting' in label:
                            entry_text2.set('0')
                        elif 'maximum' in label and 'meeting' in label:
                            entry_text2.set('5')
                        elif 'minimum' in label and 'people' in label:
                            entry_text2.set('3')
                        elif 'maximum' in label and 'people' in label:
                            entry_text2.set('5')
                    elif frame_name == 'Classroom':
                        if 'minimum' in label and 'meeting' in label:
                            entry_text2.set('0')
                        elif 'maximum' in label and 'meeting' in label:
                            entry_text2.set('2')
                        elif 'minimum' in label and 'people' in label:
                            entry_text2.set('5')
                        elif 'maximum' in label and 'people' in label:
                            entry_text2.set('19')
                    elif frame_name == 'Collaboration':
                        if 'minimum' in label and 'meeting' in label:
                            entry_text2.set('0')
                        elif 'maximum' in label and 'meeting' in label:
                            entry_text2.set('5')
                        elif 'minimum' in label and 'people' in label:
                            entry_text2.set('1')
                        elif 'maximum' in label and 'people' in label:
                            entry_text2.set('6')
                    else:
                        entry_text2.set('0')
                    entry2 = tk.Entry(frame, textvariable=entry_text2, width=20)
                else:
                    entry_text2 = tk.StringVar()
                    if frame_name == 'Conference Room':
                        if '30-min' in label:
                            entry_text2.set('25')
                        elif '60-min' in label:
                            entry_text2.set('35')
                        elif '90-min' in label:
                            entry_text2.set('25')
                        elif '120-min' in label:
                            entry_text2.set('15')
                    elif frame_name == 'Food Prep':
                        if '30-min' in label:
                            entry_text2.set('95')
                        elif '60-min' in label:
                            entry_text2.set('5')
                        elif '90-min' in label or '120-min' in label:
                            entry_text2.set('0')
                    elif frame_name == 'Classroom':
                        if '30-min' in label:
                            entry_text2.set('0')
                        elif '60-min' in label:
                            entry_text2.set('10')
                        elif '90-min' in label:
                            entry_text2.set('40')
                        elif '120-min' in label:
                            entry_text2.set('50')
                    elif frame_name == 'Collaboration':
                        entry_text2.set('25')
                    entry2 = ttk.Combobox(frame, width=20, state='readonly',
                                          textvariable=entry_text2, values=pers)

                entry2.grid(row=j + 1, column=1, padx=5, pady=5)
                page_data[label] = entry_text2

            self.frame_entries.append(page_data)
            self.frame_custom_entries.append(page_customize_data)

        self.root.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def go_office_setting(self):
        data = []
        for page_data in self.frame_entries:
            row_data = {}
            row_data['Days of week'] = page_data['Days of week'].get()
            for label in self.entry_labels:
                row_data[label] = page_data[label].get()
            data.append(row_data)

        custom_data = []
        for page_data in self.frame_custom_entries:
            row_data = {}
            row_data['Days of week'] = page_data['Days of week'].get()
            custom_data.append(row_data)

        df = pd.DataFrame(data, index=self.frame_names)
        df_custom = pd.DataFrame(custom_data, index=self.frame_names)

        df_days = df.iloc[:, 0].copy()
        df_custom_days = df_custom.iloc[:, 0].copy()
        for index in df_days.index:
            if df_days.loc[index] == 'Customize':
                df_days.loc[index] = df_custom_days.loc[index]
            if df_days.loc[index] == 'Weekdays':
                df_days.loc[index] = 'Monday, Tuesday, Wednesday, Thursday, Friday'
            if df_days.loc[index] == 'Monday - Thursday':
                df_days.loc[index] = 'Monday, Tuesday, Wednesday, Thursday'
            if df_days.loc[index] == 'Tuesday - Thursday':
                df_days.loc[index] = 'Tuesday, Wednesday, Thursday'
            if df_days.loc[index] == 'Monday - Wednesday':
                df_days.loc[index] = 'Monday, Tuesday, Wednesday'

        df.iloc[:, 0] = df_days

        check_per_lst = []
        check_number_lst = []

        df_per = df.iloc[:, -4:].astype('float64')
        df_sum = df_per.sum(axis=1)
        for idx in range(len(df_sum)):
            office = df_sum.index[idx]
            if df_sum.iloc[idx] != 100:
                check_per_lst.append(office)

        try:
            df_number = df.iloc[:, 1:5].astype('int')
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return

        if (df_number < 0).any().any():
            messagebox.showerror("Error", "Numbers for meeting and people should always be ≥ 0.")
            return

        max_cols = df_number.iloc[:, [1, -1]]
        min_cols = df_number.iloc[:, [0, 2]]
        dif_cols = pd.DataFrame(columns=['Meetings', 'People'], index=max_cols.index)
        for col in range(len(max_cols.columns)):
            dif_cols.iloc[:, col] = max_cols.iloc[:, col] > min_cols.iloc[:, col]

        for idx in range(len(dif_cols)):
            room = dif_cols.index[idx]
            if not dif_cols.all(axis=1).iloc[idx]:
                check_number_lst.append(room)

        if len(check_per_lst) == 0 and len(check_number_lst) == 0:
            summaries_path = os.path.join(self.parent.parent.save_path, config.get('summaries_folder'))
            os.makedirs(summaries_path, exist_ok=True)
            file_path = os.path.join(summaries_path,
                         f'./{self.parent.parent.time_now}_Try_Meeting rooms.csv')
            df.to_csv(file_path, index=True)

        if len(check_per_lst) > 0 and len(check_number_lst) == 0:
            messagebox.showerror(
                "Error",
                f"{', '.join(map(str, check_per_lst))}: Percentages for all meetings should add up to 100%."
            )
            return
        if len(check_per_lst) == 0 and len(check_number_lst) > 0:
            messagebox.showerror(
                "Error",
                f"{', '.join(map(str, check_number_lst))}: Maximum values should be greater than minimum values."
            )
            return
        if len(check_per_lst) > 0 and len(check_number_lst) > 0:
            messagebox.showerror(
                "Error",
                f"{', '.join(map(str, check_per_lst))}: Percentages for all meetings should add up to 100%.\n\n"
                f"{', '.join(map(str, check_number_lst))}: Maximum values should be greater than minimum values."
            )
            return

        new_input_root = tk.Toplevel(self.root)
        RoomSetting(new_input_root, self)
        self.root.withdraw()

    def on_combobox_selected(self, event, index):
        selected_option = self.frames[index].entry1.get()
        if selected_option == "Customize":
            self.frames[index].custom_entry.grid()
        else:
            self.frames[index].custom_entry.grid_remove()

    def create_tooltip(self):
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.title('Tips')
        self.tooltip.withdraw()
        self.tooltip_label = tk.Label(self.tooltip,
                                      text="In the format of: Tuesday, Wednesday, Thursday")
        self.tooltip_label.pack(padx=5, pady=5)

    def show_tooltip(self, event, index):
        x, y, _, _ = self.frames[index].custom_entry.bbox("insert")
        x += self.frames[index].custom_entry.winfo_rootx() + 25
        y += self.frames[index].custom_entry.winfo_rooty() + 25
        self.tooltip.geometry(f"+{x}+{y}")
        self.tooltip.deiconify()

    def hide_tooltip(self, event):
        self.tooltip.withdraw()

    def return_previous(self):
        self.root.destroy()
        self.parent.root.deiconify()


class SpaceInputsOffice:
    def __init__(self, root, parent):
        self.root = root
        self.root.title('Custom Offices')
        self.parent = parent
        self.frame_names = ['Open Office',
                            'Private Office',
                            'Mechanical',
                            'Shared Office']
        self.frame_entries = []
        self.num_entries = int(parent.entry_num_pages.get())

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        width = min(1600, sw)
        height = min(900, sh)
        self.root.geometry(f"{width}x{height}")

        self.create_widgets()

    def create_widgets(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        lbl_space = tk.Label(
            top_frame,
            text='Offices\nPercentages of different occupant types should add up to 100'
        )
        lbl_space.pack(side=tk.LEFT)

        self.button2 = tk.Button(top_frame, text='Save and continue',
                                 command=self.open_meeting_input)
        self.button2.pack(side=tk.RIGHT, padx=5)

        self.button3 = tk.Button(top_frame, text='Return previous',
                                 command=self.return_previous)
        self.button3.pack(side=tk.RIGHT, padx=5)

        self.lbl_status = tk.Label(self.root, text='', fg='green')
        self.lbl_status.pack(pady=5)

        container = tk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, height=600)
        h_scrollbar = tk.Scrollbar(container, orient="horizontal",
                                   command=canvas.xview)

        scroll_frame = tk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        def _on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)

        num_frames = 4
        summaries_path = os.path.join(self.parent.save_path, config.get('summaries_folder'))
        df_temp = pd.read_csv(
            f'{summaries_path}/{self.parent.time_now}_Try_Occupancy types.csv'
        )
        occupant_types = df_temp['Name'].tolist()

        pers = [str(v) for v in range(0, 101, 5)]

        for i in range(1, num_frames + 1):
            frame = ttk.LabelFrame(scroll_frame, text=self.frame_names[i - 1])
            frame.grid(row=0, column=i - 1, padx=10, pady=10, sticky="n")
            page_data = {}
            for j in range(self.num_entries + 1):
                if j == 0:
                    entry_label = 'Occupancy Density [m2/person]'
                    lbl_entry = tk.Label(frame, text=entry_label)
                    lbl_entry.grid(row=j, column=0, padx=5, pady=5)
                    entry_text = tk.StringVar(value='1')
                    entry = tk.Entry(frame, textvariable=entry_text, width=20)
                    entry.grid(row=j, column=1, padx=5, pady=5)
                else:
                    entry_label = f'occupant percentage - {occupant_types[j-1]} [%]'
                    lbl_entry = tk.Label(frame, text=entry_label)
                    lbl_entry.grid(row=j, column=0, padx=5, pady=5)
                    entry_text = tk.StringVar(value='0')
                    entry = ttk.Combobox(frame, width=20, state='readonly',
                                         textvariable=entry_text, values=pers)
                    entry.grid(row=j, column=1, padx=5, pady=5)
                page_data[entry_label] = entry_text
            self.frame_entries.append(page_data)

        self.root.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def return_previous(self):
        self.root.destroy()
        self.parent.root.deiconify()

    def open_meeting_input(self):
        data = []
        for page_data in self.frame_entries:
            row_data = {}
            for label, entry_text in page_data.items():
                row_data[label] = entry_text.get()
            data.append(row_data)

        df = pd.DataFrame(data, index=self.frame_names)
        df_per = df.iloc[:, 1:].astype('float64')
        df_sum = df_per.sum(axis=1)
        check_lst = []
        for idx in range(len(df_sum)):
            office = df_sum.index[idx]
            if df_sum.iloc[idx] != 100:
                check_lst.append(office)

        if len(check_lst) == 0:
            summaries_path = os.path.join(self.parent.save_path, config.get('summaries_folder'))
            os.makedirs(summaries_path, exist_ok=True)
            file_path = os.path.join(summaries_path,
                         f'./{self.parent.time_now}_Try_Offices.csv')
            df.to_csv(file_path, index=True)
        else:
            messagebox.showerror(
                "Error",
                "Percentages for different occupants should add up to 100% for "
                + ", ".join(map(str, check_lst))
            )
            return

        new_input_root = tk.Toplevel(self.root)
        SpaceInputsMeetings(new_input_root, self)
        self.root.withdraw()

class ViewOccDefaults:
    """
    Read-only viewer for default time distributions per occupant type
    using occ_space_options from OOS_input_template.xlsx.

    Assumes the first column contains category labels for the
    "percent of time" rows, and the following row (with NaN label)
    contains the corresponding "average stay time" values.
    """
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent
        self.root.title("Default Occupant Type Settings")

        try:
            df_raw = occ_space_options.copy()
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Could not load occ_space_options:\n\n{e}"
            )
            self.root.destroy()
            return
        if df_raw.shape[1] < 2:
            messagebox.showerror("Error", "occ_space_options must have at least 2 columns.")
            self.root.destroy()
            return

        # First column contains category labels (may be NaN on minute rows)
        cat_col = df_raw.columns[0]
        df = df_raw.copy()

        # Drop completely empty rows
        df = df.dropna(how="all")

        # Build a new index with custom labels:
        # - If category label is non-empty: "<label> - percent of time in space"
        # - If category label is NaN: use previous non-empty label and label as
        #   "<prev_label> - average time spent in space"
        new_index = []
        prev_label = None

        for _, row in df.iterrows():
            label = row[cat_col]
            if pd.isna(label) or (isinstance(label, str) and label.strip() == ""):
                # unlabeled row -> average stay time for previous category
                if prev_label is None:
                    display_label = "Unknown - average time spent in space"
                else:
                    display_label = f"{prev_label} - average time spent in space"
            else:
                # labeled row -> percent of time in space
                base_label = str(label).strip()
                display_label = f"{base_label} - percent of time in space"
                prev_label = base_label
            new_index.append(display_label)

        # Set index to our new labels; all other columns are occupant types
        df.index = new_index
        df = df.drop(columns=[cat_col])
        df.index.name = "Category - Metric"

        # -------- Layout --------
        info_label = tk.Label(
            self.root,
            text="Time distribution by space for existing occupant types\n"
                 "(If desired occupant type/configuration is not listed, you can create a new occupant type on the next screen)\n",
            justify="left"
        )
        info_label.pack(side=tk.TOP, padx=10, pady=5, anchor="w")

        container = tk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container)
        v_scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        h_scrollbar = tk.Scrollbar(container, orient="horizontal", command=canvas.xview)

        table_frame = tk.Frame(canvas)
        table_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=table_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        df_display = df.copy()

        # Header row
        tk.Label(table_frame, text=df_display.index.name or "",
                 font=("TkDefaultFont", 9, "bold"))\
            .grid(row=0, column=0, padx=4, pady=2, sticky="w")
        for col_idx, occ_type in enumerate(df_display.columns, start=1):
            tk.Label(table_frame, text=str(occ_type),
                     font=("TkDefaultFont", 9, "bold"))\
                .grid(row=0, column=col_idx, padx=4, pady=2, sticky="w")

        # Body rows
        row_gui_idx = 1
        for row_label, row_series in df_display.iterrows():
            tk.Label(table_frame, text=str(row_label),
                     font=("TkDefaultFont", 9, "bold"))\
                .grid(row=row_gui_idx, column=0, padx=4, pady=2, sticky="w")
            for col_idx, occ_type in enumerate(df_display.columns, start=1):
                value = row_series[occ_type]
                if isinstance(value, (float, int)):
                    text = f"{value:g}"
                else:
                    text = "" if pd.isna(value) else str(value)
                tk.Label(table_frame, text=text)\
                    .grid(row=row_gui_idx, column=col_idx, padx=4, pady=2, sticky="w")
            row_gui_idx += 1

        close_btn = tk.Button(self.root, text="Close", command=self.root.destroy)
        close_btn.pack(pady=5)


class AddOccType:
    def __init__(self, root, parent):
        self.root = root
        self.root.title('Add Occupant Types')
        self.parent = parent

        self.occ_umbrella_entries = []
        self.name_entries = []
        self.own_office_per_entries = []
        self.own_office_time_entries = []
        self.other_office_per_entries = []
        self.other_office_time_entries = []
        self.meeting_per_entries = []
        self.meeting_time_entries = []
        self.auxiliary_per_entries = []
        self.auxiliary_time_entries = []
        self.outdoor_per_entries = []
        self.outdoor_time_entries = []

        self.create_widgets()

    def create_widgets(self):
        lbl_num_pages = tk.Label(self.root, text="Enter number of occupant types you want to add:")
        lbl_num_pages.grid(row=0, column=0, padx=10, pady=10)

        self.entry_num_pages = tk.Entry(self.root, width=10)
        self.entry_num_pages.grid(row=0, column=1, padx=10, pady=10)

        self.btn_generate = tk.Button(self.root, text="Customize!", command=self.generate_pages)
        self.btn_generate.grid(row=0, column=2, padx=10, pady=10)

        self.btn_continue = tk.Button(self.root, text="Save and return",
                                      command=self.return_to_parent, state=tk.DISABLED)
        self.btn_continue.grid(row=0, column=3, padx=10, pady=10)

        self.lbl_status = tk.Label(self.root, text="", fg="green")
        self.lbl_status.grid(row=1, columnspan=4, padx=10, pady=10)

        self.btn_view_defaults = tk.Button(
            self.root,
            text="View default space distributions settings for pre-defined occupant types",
            command=self.open_view_defaults
        )
        self.btn_view_defaults.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

    def open_view_defaults(self):
        new_root = tk.Toplevel(self.root)
        ViewOccDefaults(new_root, self.parent)

    def generate_pages(self):
        for entry in self.occ_umbrella_entries:
            entry.destroy()
        self.occ_umbrella_entries = []

        for entry in self.name_entries:
            entry.destroy()
        self.name_entries = []

        for entry in self.own_office_per_entries:
            entry.destroy()
        self.own_office_per_entries = []

        for entry in self.own_office_time_entries:
            entry.destroy()
        self.own_office_time_entries = []

        for entry in self.other_office_per_entries:
            entry.destroy()
        self.other_office_per_entries = []

        for entry in self.other_office_time_entries:
            entry.destroy()
        self.other_office_time_entries = []

        for entry in self.meeting_per_entries:
            entry.destroy()
        self.meeting_per_entries = []

        for entry in self.meeting_time_entries:
            entry.destroy()
        self.meeting_time_entries = []

        for entry in self.auxiliary_per_entries:
            entry.destroy()
        self.auxiliary_per_entries = []

        for entry in self.auxiliary_time_entries:
            entry.destroy()
        self.auxiliary_time_entries = []

        for entry in self.outdoor_per_entries:
            entry.destroy()
        self.outdoor_per_entries = []

        for entry in self.outdoor_time_entries:
            entry.destroy()
        self.outdoor_time_entries = []

        try:
            num_pages = int(self.entry_num_pages.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return
        if num_pages <= 0:
            messagebox.showerror("Error", "Number of occupant types should be greater than zero.")
            return

        pers = []
        var = 0
        while var <= 100:
            var_str = "{}".format(var)
            pers.append(var_str)
            var += 5

        time_durations = []
        dur = 0
        while dur <= 120:
            dur_str = "{}".format(dur)
            time_durations.append(dur_str)
            dur += 5

        self.frames = []
        for i in range(num_pages):
            frame = ttk.LabelFrame(self.root, text=f"Type {i + 1}")
            frame.grid(row=2, column=i, padx=10, pady=10)
            self.frames.append(frame)

            tk.Label(frame, text="Category of occupant type").grid(row=0)
            get_umbrella = ttk.Combobox(frame, width=10, state='readonly',
                                        values=['Regular staff', 'Researcher', 'Manager', 'Administrator'])
            get_umbrella.grid(row=1)
            get_umbrella.bind("<<ComboboxSelected>>", lambda event, index=i: self.update_combobox(event, index))
            self.frames[i].get_umbrella = get_umbrella

            tk.Label(frame, text="Name of occupant type").grid(row=2)
            get_name = ttk.Combobox(frame, width=20)
            get_name.grid(row=3)
            self.frames[i].get_name = get_name

            tk.Label(frame, text="Own Office: percent of time in space (%)").grid(row=4)
            self.frames[i].own_office_per = tk.StringVar()
            self.frames[i].own_office_per.set('0')
            get_own_office_per = ttk.Combobox(frame, width=10, state='readonly',
                                              textvariable=self.frames[i].own_office_per, values=pers)
            get_own_office_per.grid(row=5)

            tk.Label(frame, text="Own Office: average time in space (min)").grid(row=6)
            self.frames[i].own_office_time = tk.StringVar()
            self.frames[i].own_office_time.set('0')
            get_own_office_time = ttk.Combobox(frame, width=10, state='readonly',
                                               textvariable=self.frames[i].own_office_time, values=time_durations)
            get_own_office_time.grid(row=7)

            tk.Label(frame, text="Other Office: percent of time in space (%)").grid(row=8)
            self.frames[i].other_office_per = tk.StringVar()
            self.frames[i].other_office_per.set('0')
            get_other_office_per = ttk.Combobox(frame, width=10, state='readonly',
                                                textvariable=self.frames[i].other_office_per, values=pers)
            get_other_office_per.grid(row=9)

            tk.Label(frame, text="Other Office: average time in space (min)").grid(row=10)
            self.frames[i].other_office_time = tk.StringVar()
            self.frames[i].other_office_time.set('0')
            get_other_office_time = ttk.Combobox(frame, width=10, state='readonly',
                                                 textvariable=self.frames[i].other_office_time, values=time_durations)
            get_other_office_time.grid(row=11)

            tk.Label(frame, text="Meeting Room: percent of time in space (%)").grid(row=12)
            self.frames[i].meeting_per = tk.StringVar()
            self.frames[i].meeting_per.set('0')
            get_meeting_per = ttk.Combobox(frame, width=10, state='readonly',
                                           textvariable=self.frames[i].meeting_per, values=pers)
            get_meeting_per.grid(row=13)

            tk.Label(frame, text="Meeting Room: average time in space (min)").grid(row=14)
            self.frames[i].meeting_time = tk.StringVar()
            self.frames[i].meeting_time.set('0')
            get_meeting_time = ttk.Combobox(frame, width=10, state='readonly',
                                            textvariable=self.frames[i].meeting_time, values=time_durations)
            get_meeting_time.grid(row=15)

            tk.Label(frame, text="Auxiliary Room: percent of time in space (%)").grid(row=16)
            self.frames[i].auxiliary_per = tk.StringVar()
            self.frames[i].auxiliary_per.set('0')
            get_auxiliary_per = ttk.Combobox(frame, width=10, state='readonly',
                                             textvariable=self.frames[i].auxiliary_per, values=pers)
            get_auxiliary_per.grid(row=17)

            tk.Label(frame, text="Auxiliary Room: average time in space (min)").grid(row=18)
            self.frames[i].auxiliary_time = tk.StringVar()
            self.frames[i].auxiliary_time.set('0')
            get_auxiliary_time = ttk.Combobox(frame, width=10, state='readonly',
                                              textvariable=self.frames[i].auxiliary_time, values=time_durations)
            get_auxiliary_time.grid(row=19)

            tk.Label(frame, text="Outdoor Room: percent of time in space (%)").grid(row=20)
            self.frames[i].outdoor_per = tk.StringVar()
            self.frames[i].outdoor_per.set('0')
            get_outdoor_per = ttk.Combobox(frame, width=10, state='readonly',
                                           textvariable=self.frames[i].outdoor_per, values=pers)
            get_outdoor_per.grid(row=21)

            tk.Label(frame, text="Outdoor Room: average time in space (min)").grid(row=22)
            self.frames[i].outdoor_time = tk.StringVar()
            self.frames[i].outdoor_time.set('0')
            get_outdoor_time = ttk.Combobox(frame, width=10, state='readonly',
                                            textvariable=self.frames[i].outdoor_time, values=time_durations)
            get_outdoor_time.grid(row=23)

            self.occ_umbrella_entries.append(get_umbrella)
            self.name_entries.append(get_name)
            self.own_office_per_entries.append(get_own_office_per)
            self.own_office_time_entries.append(get_own_office_time)
            self.other_office_per_entries.append(get_other_office_per)
            self.other_office_time_entries.append(get_other_office_time)
            self.meeting_per_entries.append(get_meeting_per)
            self.meeting_time_entries.append(get_meeting_time)
            self.auxiliary_per_entries.append(get_auxiliary_per)
            self.auxiliary_time_entries.append(get_auxiliary_time)
            self.outdoor_per_entries.append(get_outdoor_per)
            self.outdoor_time_entries.append(get_outdoor_time)

        self.btn_continue['state'] = tk.ACTIVE

    def update_combobox(self, event, index):
        selected_value = self.frames[index].get_umbrella.get()
        if selected_value == 'Regular staff':
            self.frames[index].get_name["values"] = ['janitorial', 'cleaning staff',
                                                     'maintenance staff', 'guest',
                                                     'meeting participants']
        elif selected_value == 'Researcher':
            self.frames[index].get_name["values"] = ['researcher', 'scholar', 'guest speaker']
        elif selected_value == 'Manager':
            self.frames[index].get_name["values"] = ['executive', 'boss', 'director']
        elif selected_value == 'Administrator':
            self.frames[index].get_name["values"] = ['administrator', 'supervisor']
        else:
            self.frames[index].get_name["values"] = []

    def return_to_parent(self):
        umbrellas = [entry.get() for entry in self.occ_umbrella_entries]
        names = [entry.get() for entry in self.name_entries]
        per_own_office = [entry.get() for entry in self.own_office_per_entries]
        time_own_office = [entry.get() for entry in self.own_office_time_entries]
        per_other_office = [entry.get() for entry in self.other_office_per_entries]
        time_other_office = [entry.get() for entry in self.other_office_time_entries]
        per_meeting = [entry.get() for entry in self.meeting_per_entries]
        time_meeting = [entry.get() for entry in self.meeting_time_entries]
        per_aux = [entry.get() for entry in self.auxiliary_per_entries]
        time_aux = [entry.get() for entry in self.auxiliary_time_entries]
        per_outdoor = [entry.get() for entry in self.outdoor_per_entries]
        time_outdoor = [entry.get() for entry in self.outdoor_time_entries]

        df = pd.DataFrame({"Name": names,
                           "Umbrella": umbrellas,
                           "Own Office [%]": per_own_office,
                           "Own Office [min]": time_own_office,
                           "Other Office [%]": per_other_office,
                           "Other Office [min]": time_other_office,
                           "Meeting Rooms [%]": per_meeting,
                           "Meeting Rooms [min]": time_meeting,
                           "Auxiliary [%]": per_aux,
                           "Auxiliary [min]": time_aux,
                           "Outdoor [%]": per_outdoor,
                           "Outdoor [min]": time_outdoor})
        df = df.T

        df_temp = df.iloc[[0, 1], :]
        df_count = pd.DataFrame(index=df_temp.index, columns=df_temp.columns)
        for idx in df_temp.index:
            for col in df_temp.columns:
                df_count.loc[idx, col] = len(df_temp.loc[idx, col])
        if df_count.eq(0).any().any():
            messagebox.showerror("Error", "Please enter valid names and categories.")
            return

        try:
            df_time = df.iloc[2:, :].astype('float64')
        except ValueError:
            messagebox.showerror("Error", "Please enter valid percentages and numbers.")
            return

        for i in range(5):
            df_check = df_time.iloc[2 * i:2 * (i + 1), :]
            for col in df_check.columns:
                if df_check[col].iloc[0] == 0:
                    if df_check[col].iloc[1] != 0:
                        messagebox.showerror("Error",
                                             "0 percent of time in space --> 0 minutes of time in space!")
                        return
                else:
                    if df_check[col].iloc[1] == 0:
                        messagebox.showerror("Error",
                                             "Non 0 percent of time in space --> non 0 minutes of time in space!")
                        return

        df_per = df_time.iloc[::2].astype('float64')
        df_sum = df_per.sum(axis=0)
        check_lst = []
        for user_idx in range(len(df_sum)):
            user = names[user_idx]
            sum_value = df_sum.loc[df_sum.index[user_idx]]
            if not sum_value == 100:
                check_lst.append(user)

        if len(check_lst) == 0:
            summaries_path = os.path.join(self.parent.save_path, config.get('summaries_folder'))
            os.makedirs(summaries_path, exist_ok=True)
            file_path = os.path.join(summaries_path,
                         f"./{self.parent.time_now}_Added Occupancy types.csv")
            df.to_csv(file_path, index=False, header=False)
        else:
            messagebox.showerror(
                "Error",
                f"Percentages of each room for occupant type(s) "
                f"{'%s' % ', '.join(map(str, check_lst))} should add up to 100.")
            return

        self.root.destroy()


class OccInput:
    def __init__(self, root):
        self.root = root
        self.root.title("Custom Occupancy Configuration")
        self.time_now = datetime.datetime.now().strftime('%Y-%m-%d_%H_%M')
        # Validate configuration
        missing_paths = config.validate_paths()
        if missing_paths:
            error_msg = "Missing required files/folders:\n\n" + "\n".join(missing_paths)
            error_msg += "\n\nPlease check your installation or edit config.json"
            messagebox.showerror("Configuration Error", error_msg)
            self.root.quit()
            return
        self.name_box = ['Manager', 'Regular Staff', 'Recluse', 'Social',
                         'Meeting Heavy', 'Maintenance', 'Cleaning']
        self.name_entries = []
        self.arrival_entries = []
        self.arrival_var_entries = []
        self.departure_entries = []
        self.departure_var_entries = []
        self.frames = []
        self.cwd = config.get('project_root')
        self.save_path = os.path.join(config.get('simulation_output'), f'{self.time_now}')
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        self.create_widgets()

    def create_widgets(self):
        lbl_num_pages = tk.Label(self.root, text="Select number of occupant types:")
        lbl_num_pages.grid(row=0, column=0, padx=10, pady=10)
        self.entry_num_pages = tk.Entry(self.root, width=10)
        self.entry_num_pages.grid(row=0, column=1, padx=10, pady=10)

        self.btn_generate = tk.Button(self.root, text="Next", command=self.generate_pages)
        self.btn_generate.grid(row=0, column=2, padx=10, pady=10)

        self.add_page_btn = tk.Button(self.root, text='Add existing or new occupant type',
                                      command=self.add_occ_frame, state=tk.DISABLED)
        self.add_page_btn.grid(row=1, column=3, padx=3, pady=10)

        self.btn_continue = tk.Button(self.root, text='Save and continue',
                                      command=self.open_space_type_input, state=tk.DISABLED)
        self.btn_continue.grid(row=0, column=3, padx=10, pady=10)

        self.btn_view_defaults = tk.Button(
            self.root,
            text="View default space distribution settings for existing occupant types",
            command=self.open_view_defaults
        )
        self.btn_view_defaults.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.lbl_status = tk.Label(self.root, text="", fg="green")
        self.lbl_status.grid(row=1, columnspan=4, padx=10, pady=10)

    def open_view_defaults(self):
        new_root = tk.Toplevel(self.root)
        ViewOccDefaults(new_root, self)

    def generate_pages(self):
        self.add_page_btn['state'] = tk.ACTIVE
        self.btn_continue['state'] = tk.ACTIVE

        for frame in self.frames:
            frame.destroy()
        self.frames = []

        for entry in self.name_entries:
            entry.destroy()
        self.name_entries = []

        for entry in self.arrival_entries:
            entry.destroy()
        self.arrival_entries = []

        for entry in self.arrival_var_entries:
            entry.destroy()
        self.arrival_var_entries = []

        for entry in self.departure_entries:
            entry.destroy()
        self.departure_entries = []

        for entry in self.departure_var_entries:
            entry.destroy()
        self.departure_var_entries = []

        self.btn_generate.config(text="Try again")

        try:
            num_pages = int(self.entry_num_pages.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return
        if num_pages <= 0:
            messagebox.showerror("Error", "Number of occupant types should be greater than zero.")
            return

        self.time_intervals = []
        start_hour = 0
        start_minute = 0
        while start_hour < 24:
            time_str = "{:02}:{:02}".format(start_hour, start_minute)
            self.time_intervals.append(time_str)
            start_minute += 30
            if start_minute >= 60:
                start_hour += 1
                start_minute = 0

        self.time_vars = []
        var = 0
        while var <= 60:
            var_str = "{}".format(var)
            self.time_vars.append(var_str)
            var += 5

        self.time_durations = []
        dur = 0
        while dur <= 120:
            dur_str = "{}".format(dur)
            self.time_durations.append(dur_str)
            dur += 15

        try:
            file_path = os.path.join(self.save_path,
                                     f'./{self.time_now}_Added Occupancy types.csv')
            df_new_name = pd.read_csv(file_path)
            new_names = df_new_name.columns.tolist()
            self.name_box += new_names
        except Exception:
            pass

        for i in range(num_pages):
            frame = ttk.LabelFrame(self.root, text=f"Type {i + 1}")
            frame.grid(row=3, column=i, padx=10, pady=10)
            self.frames.append(frame)

            tk.Label(frame, text="Name of occupant type").pack()
            get_name = ttk.Combobox(frame, width=10, state='readonly', values=self.name_box)
            get_name.pack()
            get_name.bind("<<ComboboxSelected>>", lambda event, index=i: self.update_combobox(event, index))
            self.frames[i].get_name = get_name

            tk.Label(frame, text="Arrival time (hh:mm)").pack()
            get_arrival = ttk.Combobox(frame, width=10, state='readonly',
                                       values=self.time_intervals)
            get_arrival.pack()
            self.frames[i].get_arrival = get_arrival

            tk.Label(frame, text="Variation in arrival time (min)").pack()
            get_arrival_var = ttk.Combobox(frame, width=10, state='readonly',
                                           values=self.time_vars)
            get_arrival_var.pack()
            self.frames[i].get_arrival_var = get_arrival_var

            tk.Label(frame, text="Departure time (hh:mm)").pack()
            get_departure = ttk.Combobox(frame, width=10, state='readonly',
                                         values=self.time_intervals)
            get_departure.pack()
            self.frames[i].get_departure = get_departure

            tk.Label(frame, text="Variation in departure time (min)").pack()
            get_departure_var = ttk.Combobox(frame, width=10, state='readonly',
                                             values=self.time_vars)
            get_departure_var.pack()
            self.frames[i].get_departure_var = get_departure_var

            lbl_num_st = tk.Label(frame, text="Numbers of short time leavings:")
            lbl_num_st.pack()
            str_num_st = tk.StringVar()
            entry_num_st = tk.Entry(frame, width=10, textvariable=str_num_st)
            entry_num_st.pack()
            btn_st_leaving = tk.Button(frame, text="Next",
                                       command=lambda index=i: self.generate_sts(index))
            btn_st_leaving.pack(pady=5)
            btn_st_reset = tk.Button(frame, text='Reset to 0',
                                     command=lambda index=i: self.reset_sts(index),
                                     state=tk.DISABLED)
            btn_st_reset.pack(pady=5)

            self.frames[i].str_num_st = str_num_st
            self.frames[i].entry_num_st = entry_num_st
            self.frames[i].btn_st_leaving = btn_st_leaving
            self.frames[i].btn_st_reset = btn_st_reset

            self.name_entries.append(get_name)
            self.arrival_entries.append(get_arrival)
            self.arrival_var_entries.append(get_arrival_var)
            self.departure_entries.append(get_departure)
            self.departure_var_entries.append(get_departure_var)

        added_frame = ttk.LabelFrame(self.root)
        added_frame.grid(row=3, column=num_pages, padx=10, pady=10)
        self.frames.append(added_frame)
        add_btn = tk.Button(added_frame, text='Create new, customized occupant type',
                            command=self.add_occ_type)
        add_btn.grid(row=2, padx=20, pady=20)
        refresh_button = tk.Button(added_frame,
                                   text='Add new, customized occupant type\nto the dropdown list',
                                   command=self.add_new_occ_type_to_lst)
        refresh_button.grid(row=3, padx=20, pady=20)

    def add_occ_frame(self):
        self.frames[-1].destroy()
        self.frames = self.frames[:-1]
        num_pages = int(len(self.frames)) + 1
        for i in range(num_pages):
            try:
                frame = self.frames[i]
            except IndexError:
                frame = ttk.LabelFrame(self.root, text=f"Type {i + 1}")
                frame.grid(row=3, column=i, padx=10, pady=10)
                self.frames.append(frame)

                tk.Label(frame, text="Name of occupant type").pack()
                get_name = ttk.Combobox(frame, width=10, state='readonly', values=self.name_box)
                get_name.pack()
                get_name.bind("<<ComboboxSelected>>", lambda event, index=i: self.update_combobox(event, index))
                self.frames[i].get_name = get_name

                tk.Label(frame, text="Arrival time (hh:mm)").pack()
                get_arrival = ttk.Combobox(frame, width=10, state='readonly',
                                           values=self.time_intervals)
                get_arrival.pack()
                self.frames[i].get_arrival = get_arrival

                tk.Label(frame, text="Variation in arrival time (min)").pack()
                get_arrival_var = ttk.Combobox(frame, width=10, state='readonly',
                                               values=self.time_vars)
                get_arrival_var.pack()
                self.frames[i].get_arrival_var = get_arrival_var

                tk.Label(frame, text="Departure time (hh:mm)").pack()
                get_departure = ttk.Combobox(frame, width=10, state='readonly',
                                             values=self.time_intervals)
                get_departure.pack()
                self.frames[i].get_departure = get_departure

                tk.Label(frame, text="Variation in departure time (min)").pack()
                get_departure_var = ttk.Combobox(frame, width=10, state='readonly',
                                                 values=self.time_vars)
                get_departure_var.pack()
                self.frames[i].get_departure_var = get_departure_var

                lbl_num_st = tk.Label(frame, text="Numbers of short time leavings:")
                lbl_num_st.pack()
                str_num_st = tk.StringVar()
                entry_num_st = tk.Entry(frame, width=10, textvariable=str_num_st)
                entry_num_st.pack()
                btn_st_leaving = tk.Button(frame, text="Next",
                                           command=lambda index=i: self.generate_sts(index))
                btn_st_leaving.pack(pady=5)
                btn_st_reset = tk.Button(frame, text='Reset to 0',
                                         command=lambda index=i: self.reset_sts(index),
                                         state=tk.DISABLED)
                btn_st_reset.pack(pady=5)

                self.frames[i].str_num_st = str_num_st
                self.frames[i].entry_num_st = entry_num_st
                self.frames[i].btn_st_leaving = btn_st_leaving
                self.frames[i].btn_st_reset = btn_st_reset

                self.name_entries.append(get_name)
                self.arrival_entries.append(get_arrival)
                self.arrival_var_entries.append(get_arrival_var)
                self.departure_entries.append(get_departure)
                self.departure_var_entries.append(get_departure_var)
            continue

        added_frame = ttk.LabelFrame(self.root)
        added_frame.grid(row=3, column=num_pages, padx=10, pady=10)
        self.frames.append(added_frame)
        add_btn = tk.Button(added_frame, text='Customize occupant type',
                            command=self.add_occ_type)
        add_btn.grid(row=2, padx=20, pady=20)
        refresh_button = tk.Button(added_frame,
                                   text='Add customized occupant type\n'
                                        'to the dropdown list',
                                   command=self.add_new_occ_type_to_lst)
        refresh_button.grid(row=3, padx=20, pady=20)

        self.entry_num_pages.delete(0, tk.END)
        self.entry_num_pages.insert(0, f'{len(self.frames)-1}')

    def add_new_occ_type_to_lst(self):
        try:
            file_path = os.path.join(self.save_path,
                                     f'./{self.time_now}_Added Occupancy types.csv')
            df_new_name = pd.read_csv(file_path)
            new_names = df_new_name.columns.tolist()
            self.name_box += new_names
        except Exception:
            messagebox.showerror("Error", "Please customize new occupancy type and save first!")
            return

        for idx in range(len(self.frames)-1):
            self.frames[idx].get_name['values'] = self.name_box

    def reset_sts(self, index):
        for entry_widget in getattr(self.frames[index], "widgets", []):
            entry_widget.destroy()
        for entry_widget in getattr(self.frames[index], "widget_page", []):
            entry_widget.destroy()
        self.frames[index].str_num_st.set('0')

    def generate_sts(self, index):
        self.frames[index].btn_st_reset['state'] = tk.ACTIVE
        self.frames[index].widgets = []
        self.frames[index].widget_page = []
        try:
            num_pages = int(self.frames[index].entry_num_st.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            return
        if num_pages < 0:
            messagebox.showerror("Error", "Number of short-term leavings should be ≥ zero.")
            return

        for widget_num in range(num_pages):
            widget = ttk.LabelFrame(self.frames[index])
            widget.pack()
            self.frames[index].widget_page.append(widget)

            tk.Label(widget, text="Short-term leaving time (hh:mm)").pack()
            get_short_term = ttk.Combobox(widget, width=10, state='readonly',
                                          values=self.time_intervals)
            get_short_term.pack()
            self.frames[index].widget_page[widget_num].get_short_term = get_short_term

            tk.Label(widget, text="Variation in short-term leaving time (min)").pack()
            get_short_term_var = ttk.Combobox(widget, width=10, state='readonly',
                                              values=self.time_vars)
            get_short_term_var.pack()
            self.frames[index].widget_page[widget_num].get_short_term_var = get_short_term_var

            tk.Label(widget, text="Short-term leaving duration (min)").pack()
            get_short_term_dur = ttk.Combobox(widget, width=10, state='readonly',
                                              values=self.time_durations)
            get_short_term_dur.pack()
            self.frames[index].widget_page[widget_num].get_short_term_dur = get_short_term_dur

            tk.Label(widget, text="Variation in short-term leaving duration (min)").pack()
            get_short_term_dur_var = ttk.Combobox(widget, width=10, state='readonly',
                                                  values=self.time_vars)
            get_short_term_dur_var.pack()
            self.frames[index].widget_page[widget_num].get_short_term_dur_var = get_short_term_dur_var

            self.frames[index].widgets.append(get_short_term)
            self.frames[index].widgets.append(get_short_term_var)
            self.frames[index].widgets.append(get_short_term_dur)
            self.frames[index].widgets.append(get_short_term_dur_var)

    def update_combobox(self, event, index):
        selected_value = self.frames[index].get_name.get()

        predefined_arr = {
            'Manager': '10:00',
            'Regular Staff': '09:00',
            'Recluse': '11:00',
            'Social': '09:30',
            'Meeting Heavy': '09:30',
            'Maintenance': '07:00',
            'Cleaning': '19:00'
        }
        predefined_var = {
            'Manager': '30',
            'Regular Staff': '30',
            'Recluse': '60',
            'Social': '60',
            'Meeting Heavy': '60',
            'Maintenance': '15',
            'Cleaning': '15'
        }
        predefined_dep = {
            'Manager': '17:00',
            'Regular Staff': '17:00',
            'Recluse': '19:00',
            'Social': '16:30',
            'Meeting Heavy': '16:30',
            'Maintenance': '14:00',
            'Cleaning': '21:00'
        }
        predefined_st_leaving = {
            'Manager': '12:00',
            'Regular Staff': '12:00',
            'Recluse': '14:00',
            'Social': '12:00',
            'Meeting Heavy': '14:00',
            'Maintenance': '11:00'
        }
        predefined_st_leaving_var = {
            'Manager': '30',
            'Regular Staff': '30',
            'Recluse': '60',
            'Social': '60',
            'Meeting Heavy': '30',
            'Maintenance': '30'
        }
        predefined_st_leaving_dur = {
            'Manager': '60',
            'Regular Staff': '45',
            'Recluse': '60',
            'Social': '60',
            'Meeting Heavy': '60',
            'Maintenance': '45'
        }
        predefined_st_leaving_dur_var = {
            'Manager': '30',
            'Regular Staff': '15',
            'Recluse': '30',
            'Social': '30',
            'Meeting Heavy': '30',
            'Maintenance': '15'
        }

        if selected_value in predefined_arr:
            self.frames[index].get_arrival.set(predefined_arr[selected_value])
        else:
            self.frames[index].get_arrival.set("09:00")

        if selected_value in predefined_dep:
            self.frames[index].get_departure.set(predefined_dep[selected_value])
        else:
            self.frames[index].get_departure.set("17:00")

        if selected_value in predefined_var:
            self.frames[index].get_arrival_var.set(predefined_var[selected_value])
            self.frames[index].get_departure_var.set(predefined_var[selected_value])
        else:
            self.frames[index].get_arrival_var.set("30")
            self.frames[index].get_departure_var.set("30")

        try:
            num_widgets = int(self.frames[index].entry_num_st.get())
            for num_w in range(num_widgets):
                if selected_value in predefined_st_leaving:
                    self.frames[index].widget_page[num_w].get_short_term.set(
                        predefined_st_leaving[selected_value])
                if selected_value in predefined_st_leaving_var:
                    self.frames[index].widget_page[num_w].get_short_term_var.set(
                        predefined_st_leaving_var[selected_value])
                if selected_value in predefined_st_leaving_dur:
                    self.frames[index].widget_page[num_w].get_short_term_dur.set(
                        predefined_st_leaving_dur[selected_value])
                if selected_value in predefined_st_leaving_dur_var:
                    self.frames[index].widget_page[num_w].get_short_term_dur_var.set(
                        predefined_st_leaving_dur_var[selected_value])
        except Exception:
            pass

    def add_occ_type(self):
        new_input_root1 = tk.Toplevel(self.root)
        AddOccType(new_input_root1, self)

    def open_space_type_input(self):
        names = [entry.get() for entry in self.name_entries]
        arrivals = [entry.get() for entry in self.arrival_entries]
        arrival_vars = [entry.get() for entry in self.arrival_var_entries]
        departures = [entry.get() for entry in self.departure_entries]
        departure_vars = [entry.get() for entry in self.departure_var_entries]

        st_headings = ["Short-term leaving time [hh:mm]",
                       "Variation in short-term leaving time [min]",
                       "Short-term leaving duration [min]",
                       "Variation in short-term leaving duration [min]"]

        df = pd.DataFrame({"Name": names,
                           "Arrival time [hh:mm]": arrivals,
                           "Variation in arrival time [min]": arrival_vars,
                           "Departure time [hh:mm]": departures,
                           "Variation in departure time [min]": departure_vars})
        df['Arrival time [hh:mm]'] = pd.to_datetime(df['Arrival time [hh:mm]'],
                                                   format='%H:%M').dt.time
        df['Departure time [hh:mm]'] = pd.to_datetime(df['Departure time [hh:mm]'],
                                                     format='%H:%M').dt.time
        df.set_index(df['Name'], inplace=True)

        dic_st = {}
        for frame_idx in range(len(self.frames) - 1):
            values = []
            frame = self.frames[frame_idx]
            name = names[frame_idx]
            try:
                for entry in frame.widgets:
                    val = entry.get()
                    values.append(val)
                    dic_st[name] = values
            except Exception:
                dic_st[name] = values

        max_len = max(len(v) for v in dic_st.values())
        st_data = {k: v + [''] * (max_len - len(v)) for k, v in dic_st.items()}
        df_st = pd.DataFrame(st_data).T
        cols = st_headings * (int(max_len / 4))
        df_st.columns = cols
        for col_id in range(len(cols)):
            if df_st.columns[col_id] == st_headings[0]:
                df_st.iloc[:, col_id] = pd.to_datetime(df_st.iloc[:, col_id],
                                                       format='%H:%M').dt.time

        df = df.join(df_st)
        df.replace({np.nan: ''}, inplace=True)

        check_lst = []
        for idx in range(len(names)):
            h_arr = int(arrivals[idx].split(':')[0])
            m_arr = int(arrivals[idx].split(':')[1])
            h_dep = int(departures[idx].split(':')[0])
            m_dep = int(departures[idx].split(':')[1])
            t_delta = (m_dep - m_arr) + (h_dep - h_arr) * 60
            if t_delta <= 0:
                check_lst.append(names[idx])

        if len(check_lst) == 0:
            summaries_path = os.path.join(self.save_path, config.get('summaries_folder'))
            os.makedirs(summaries_path, exist_ok=True)
            file_path = os.path.join(summaries_path,
                             f"./{self.time_now}_Try_Occupancy types.csv")
            df.to_csv(file_path, index=False)
        else:
            messagebox.showerror(
                "Error",
                "Departure time should be greater than arrival time for "
                + ", ".join(map(str, check_lst))
            )
            return

        new_input_root = tk.Toplevel(self.root)
        SpaceInputsOffice(new_input_root, self)
        self.root.withdraw()

if __name__ == '__main__':
    matplotlib.use('Qt5Agg')
    warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)
    pd.options.mode.chained_assignment = None
    root = tk.Tk()
    app = OccInput(root)
    root.mainloop()