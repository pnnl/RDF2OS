"""
Configuration management for OOS GUI application.
Reads settings from user_settings.py and derives all file paths automatically.
"""

import os
import platform
import datetime
import xml.etree.ElementTree as et

import user_settings as settings


class Config:
    """Manages application configuration, derived paths, and XML settings."""
    
    VALID_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday", "Sunday"]
    
    def __init__(self):
        self.paths = {}
        
        # Build user_config directly from user_settings.py
        self.user_config = {
            'project_root': settings.PROJECT_ROOT
        }
        
        self._validate_user_settings()
        self._derive_paths()
        self._update_obcosim_xml()
    
    def _validate_user_settings(self):
        """Validate all values in user_settings.py before proceeding."""
        errors = []
        
        if not os.path.isdir(settings.PROJECT_ROOT):
            errors.append(f"PROJECT_ROOT does not exist: {settings.PROJECT_ROOT}")
        
        if settings.START_DAY_OF_WEEK not in self.VALID_DAYS:
            errors.append(
                f"START_DAY_OF_WEEK must be one of {self.VALID_DAYS}, "
                f"got: '{settings.START_DAY_OF_WEEK}'"
            )
        
        if not isinstance(settings.IS_LEAP_YEAR, bool):
            errors.append("IS_LEAP_YEAR must be True or False")
        
        if 60 % settings.TIMESTEPS_PER_HOUR != 0:
            errors.append(
                f"TIMESTEPS_PER_HOUR ({settings.TIMESTEPS_PER_HOUR}) must evenly "
                f"divide 60. Valid values: 1,2,3,4,5,6,10,12,15,20,30,60"
            )
        
        year = 2016 if settings.IS_LEAP_YEAR else 2018
        start_date = None
        end_date = None
        
        try:
            start_date = datetime.date(year, settings.START_MONTH, settings.START_DAY)
        except ValueError as e:
            errors.append(f"Invalid START_MONTH/START_DAY: {e}")
        
        try:
            end_date = datetime.date(year, settings.END_MONTH, settings.END_DAY)
        except ValueError as e:
            errors.append(f"Invalid END_MONTH/END_DAY: {e}")
        
        if start_date and end_date:
            if end_date < start_date:
                errors.append(
                    "END date must be after START date "
                    "(simulation cannot cross year boundaries)"
                )
            else:
                num_days = (end_date - start_date).days + 1
                max_days = 366 if settings.IS_LEAP_YEAR else 365
                if num_days > max_days:
                    errors.append(
                        f"Simulation period is {num_days} days, exceeding "
                        f"the {max_days}-day maximum for a "
                        f"{'leap' if settings.IS_LEAP_YEAR else 'non-leap'} year"
                    )
                self._num_days = num_days
        
        if errors:
            error_list = "\n".join(f"  ✗ {e}" for e in errors)
            raise ValueError(
                f"\n{'='*70}\n"
                f"Invalid settings in user_settings.py:\n"
                f"{'='*70}\n"
                f"{error_list}\n"
                f"{'='*70}\n"
                f"Please fix these values and try again.\n"
                f"{'='*70}\n"
            )
    
    def _derive_paths(self):
        """Derive all other paths from user-provided configuration."""
        self.paths = self.user_config.copy()
        
        project_root = self.paths.get('project_root')
        if not project_root:
            raise ValueError(
                f"\n{'='*70}\n"
                f"'project_root' not found in user_settings.py!\n"
                f"{'='*70}\n"
            )
        
        print(f"✓ Project root: {project_root}")
        
        supporting_files = os.path.join(project_root, 'Supporting_Files')
        
        # Determine correct FMU executable based on OS
        system = platform.system()
        if system == 'Windows':
            fmu_name = 'obFMU.exe'
        elif system == 'Linux':
            fmu_name = 'obFMU_linux'
        elif system == 'Darwin':  # macOS
            fmu_name = 'obFMU_mac'
        else:
            fmu_name = 'obFMU.exe'  # fallback
        
        try:
            self.paths.update({
                'supporting_files': supporting_files,
                'obcosim_xml': os.path.join(supporting_files, 'obCoSim.xml'),
                'fmu_executable': os.path.join(supporting_files, 'FMUs', fmu_name),
                'ttl_directory': os.path.join(supporting_files, 'Semantic_Files'),
                'building_ttl': os.path.join(supporting_files, 'Semantic_Files', 'bldg2_AC_V1_PNNL.ttl'),
                'ontology_ttl': os.path.join(supporting_files, 'Semantic_Files', 'Ontology.ttl'),
                'workdays_file': os.path.join(project_root, 'workdays.csv'),
                
                # Output paths (auto-generated at runtime) - now in project_root
                'simulation_output': os.path.join(project_root, 'simulation_results'),
                'raw_simulation_data': 'raw_simulation_data',
                'plots_folder': 'plots',
                'summaries_folder': 'simulation_summaries',
                'output_xml': os.path.join(supporting_files, 'output_xml.xml'),
                'occupant_space_dict': os.path.join(supporting_files, 'occupant_space_dict.xlsx'),
                'timer_output': os.path.join(supporting_files, 'timer_output.json'),
                
                # Simulation settings
                'sim_start_day_of_week': settings.START_DAY_OF_WEEK,
                'sim_is_leap_year': settings.IS_LEAP_YEAR,
                'sim_start_month': settings.START_MONTH,
                'sim_start_day': settings.START_DAY,
                'sim_end_month': settings.END_MONTH,
                'sim_end_day': settings.END_DAY,
                'sim_timesteps_per_hour': settings.TIMESTEPS_PER_HOUR,
                'sim_num_days': self._num_days,
            })
            print(f"✓ Derived {len(self.paths) - len(self.user_config)} auto-derived paths")
            print(f"✓ Detected OS: {system} → using FMU: {fmu_name}")
            
        except Exception as e:
            raise RuntimeError(
                f"\n{'='*70}\n"
                f"Error deriving paths from project_root!\n"
                f"{'='*70}\n"
                f"{str(e)}\n"
                f"{'='*70}\n"
            )
    
    def _update_obcosim_xml(self):
        """Write user's simulation settings into obCoSim.xml automatically."""
        xml_path = self.paths['obcosim_xml']
        
        if not os.path.exists(xml_path):
            raise FileNotFoundError(
                f"\n{'='*70}\n"
                f"obCoSim.xml not found at expected location:\n"
                f"{xml_path}\n"
                f"{'='*70}\n"
                f"Check that PROJECT_ROOT in user_settings.py is correct.\n"
                f"{'='*70}\n"
            )
        
        tree = et.parse(xml_path)
        root = tree.getroot()
        sim_settings = root.find('SimulationSettings')
        
        sim_settings.find('IsLeapYear').text = 'Yes' if settings.IS_LEAP_YEAR else 'No'
        sim_settings.find('DayofWeekForStartDay').text = settings.START_DAY_OF_WEEK
        sim_settings.find('StartMonth').text = str(settings.START_MONTH)
        sim_settings.find('StartDay').text = str(settings.START_DAY)
        sim_settings.find('EndMonth').text = str(settings.END_MONTH)
        sim_settings.find('EndDay').text = str(settings.END_DAY)
        sim_settings.find('NumberofTimestepsPerHour').text = str(settings.TIMESTEPS_PER_HOUR)
        
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        print(f"✓ Updated obCoSim.xml with your simulation settings:")
        print(f"  Period: {settings.START_MONTH}/{settings.START_DAY} "
              f"to {settings.END_MONTH}/{settings.END_DAY} "
              f"({self._num_days} days)")
        print(f"  Timestep: {60 // settings.TIMESTEPS_PER_HOUR} minutes")
        print(f"  Start day: {settings.START_DAY_OF_WEEK}")
    
    def validate_paths(self):
        """Check that all required files/directories exist."""
        missing = []
        
        required_files = [
            'workdays_file', 'obcosim_xml', 'building_ttl', 'ontology_ttl',
            'fmu_executable'
        ]
        for key in required_files:
            path = self.paths.get(key)
            if not path or not os.path.exists(path):
                missing.append(f"{key}: {path}")
        
        required_dirs = ['project_root', 'supporting_files', 'ttl_directory']
        for key in required_dirs:
            path = self.paths.get(key)
            if not path or not os.path.isdir(path):
                missing.append(f"{key}: {path}")
        
        return missing
    
    def get(self, key, default=None):
        """Get a configuration value by key."""
        value = self.paths.get(key, default)
        if value is None:
            raise KeyError(
                f"Configuration key '{key}' not found. "
                f"Available keys: {list(self.paths.keys())}"
            )
        return value
    
    def print_config(self):
        """Print current configuration for debugging."""
        print("\n" + "="*70)
        print("Configuration Summary")
        print("="*70)
        for key in sorted(self.paths.keys()):
            value = self.paths[key]
            if isinstance(value, str) and (os.sep in value or '/' in value):
                status = "✓" if os.path.exists(value) else "✗"
            else:
                status = " "
            print(f"{status} {key:25s} = {value}")
        print("="*70 + "\n")


# Global config instance
try:
    config = Config()
except (FileNotFoundError, ValueError) as e:
    print(str(e))
    import sys
    sys.exit(1)

# Validate paths on import
_missing = config.validate_paths()
if _missing:
    print("\n" + "="*70)
    print("Missing required files/directories:")
    print("="*70)
    for item in _missing:
        print(f"  ✗ {item}")
    print("="*70)
    print("\nCheck PROJECT_ROOT in user_settings.py and your folder structure.\n")
    import sys
    sys.exit(1)