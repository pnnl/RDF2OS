import pandas as pd
import datetime
import random
import xml.etree.ElementTree as et
import math

class Timer():
    def __init__(self) -> None:
        self.start_time = 0
        self.read_input_time = 0
        self.build_python_object_time = 0
        self.build_xml_time = 0
        self.run_simulation_time = 0

class Inputs:
    def __init__(self, input_filename):
        '''Create an object containing the inputs for the program.
        '''
        self.office_definitions = ['office', 'mechanical'] # List of space type names that can be categorized as office spaces
        self.meeting_room_definitions = ['collaboration', 'conference room', 'meeting', 'food prep', 'classroom'] # List of space type names that can be categorized as meeting spaces
        # self.other_spaces_definitions = ['mechanical', 'other']
        self.read_space_type_input_spreadsheet(input_filename) #Read space type input spreadsheet and add variables to object
        self.read_occupant_behavior_input_spreadsheet(input_filename) #Read occupant type input spreadsheet and add variables to input object
        self.read_space_input_spreadsheet(input_filename) # Read space input spreadsheet
        year_of_analysis = 2016 #Year for which the simulation is run
        self.list_of_holidays = [f'{year_of_analysis}-01-01',
                                 f'{year_of_analysis}-01-18',
                                 f'{year_of_analysis}-02-15',
                                 f'{year_of_analysis}-05-30',
                                 f'{year_of_analysis}-07-04',
                                 f'{year_of_analysis}-09-05',
                                 f'{year_of_analysis}-10-10',
                                 f'{year_of_analysis}-11-11',
                                 f'{year_of_analysis}-11-24',
                                 f'{year_of_analysis}-12-25'] #List of holidays in format YYYY-MM-DD
        
        self.sort_flag = False
        self.occupant_sort_order = ['Manager', 'Regular staff', 'Administrator', 'Janitorial staff']
        if self.sort_flag:
            for name in self.occupant_sort_order:
                if name not in self.behavior_type_list:
                    raise Exception(f"Occupant type {name} in occupant sort order does not have a definition in the the occupant behavior input {input_filename}.")

    def read_space_input_spreadsheet(self, input_filename: str):
        '''Read the space input spreadsheet.
        '''
        self.space_input_df = pd.read_excel(input_filename, sheet_name = 'space_input') #Read the excel file 
        check_result = self.check_space_input_df_format(self.space_input_df) #Run checks to make sure the space input is in the right format
        if not check_result:
            raise Exception('Incorrect format used for space input spreadsheet') #Raise an error if the spreadsheet is not in the right format

    def read_space_type_input_spreadsheet(self, input_filename: str):
        '''Read the space type input spreadsheet.
        '''
        space_type_input_df = pd.read_excel(input_filename, sheet_name = 'space_type_input')
        self.space_type_list = []
        self.office_space_type_list = []
        self.meeting_room_space_type_list = []
        self.space_types = {}
        columns = space_type_input_df.columns

        if len(columns) % 2 != 0: #Check for even number of columns
            raise Exception("Incorrect number of columns in space types input")
        for i in range(int(len(columns)/2)): #Iterate through columns in pairs
            sliced_columns = space_type_input_df.iloc[:, 2*i:(2*i+2)] #Slice required columns from rest of DF
            umbrella_type = self.get_space_type_umbrella_term(sliced_columns.columns[0]) #Get basic space type definition as defined by the simulator: SharedOffice, MeetingRoom, Other. Other does not need to be configured
            if umbrella_type == 'OfficeShared':
                space_type = OfficeSpaceType(sliced_columns) #Add office space type object to the input object
                self.office_space_type_list.append(space_type.name) #Collect list of office space type objects
            elif umbrella_type == 'MeetingRoom':
                space_type = MeetingSpaceType(sliced_columns) #Add meeting space type object to input object
                self.meeting_room_space_type_list.append(space_type.name) #Collect list of meeting space type objects
            else:
                raise Exception(f"Invalid space type format {sliced_columns.iloc[0, 0]} in space types input")
            
            space_type_name = space_type.name
            self.space_type_list.append(space_type_name) #Collect master list of space types
            self.space_types[space_type_name] = space_type #Add key, value pair to dictionary of space type objects

    def get_space_type_umbrella_term(self, space_type: str):
        '''Get space type definitions that are provided by program based on the 
        space type name. Uses office and meeting room definitions as defined in 
        initialization of input object.
        '''
        umbrella_term_dict = {
            'OfficeShared': self.office_definitions,
            'MeetingRoom': self.meeting_room_definitions
        }

        required_term = ''
        for umbrella_term in umbrella_term_dict.keys():
            for definition in umbrella_term_dict[umbrella_term]:
                if definition.lower() in space_type.lower():
                    required_term = umbrella_term
                    break

        if required_term == '':
            raise Exception(f'Required term not found for space type {space_type} in lines 11-12 in occSim_classes.py.')
        return required_term

    def read_occupant_behavior_input_spreadsheet(self, input_filename: str):
        '''Read occupant behavior input spreadsheet.
        '''
        occupant_behavior_input_df = pd.read_excel(input_filename, sheet_name = 'behavior_input')
        self.behavior_type_list = []
        self.behaviors = {}
        columns = occupant_behavior_input_df.columns

        if len(columns) % 2 != 0: #Check for even number of columns
            raise Exception("Incorrect number of columns in space types input")
        for i in range(int(len(columns)/2)): #Go through columns in pairs
            sliced_columns = occupant_behavior_input_df.iloc[:, 2*i:(2*i+2)] #Slice required columns
            behavior = BehaviorType(sliced_columns) #Add behavior type object to the input object
            
            behavior_type_name = behavior.name
            self.behavior_type_list.append(behavior_type_name) #Collect list of behavior types
            self.behaviors[behavior_type_name] = behavior #Collect dict of behavior type names and objects

    def return_behaviors_section_xml_string(self):
        '''Return XMl string for behaviors section.
        '''
        behaviors = et.Element('Behaviors')

        for behavior_name in self.behavior_type_list:
            behavior = self.behaviors[behavior_name]
            behavior_string = behavior.return_xml_string()
            behavior_element = et.fromstring(behavior_string)
            behaviors.append(behavior_element)

        xml_string = et.tostring(behaviors)
        return xml_string

    def return_holidays_section_xml_string(self):
        '''Return XML string for the holidays section.
        '''
        holidays = et.Element('Holidays')

        for holiday_string in self.list_of_holidays:
            holiday = et.Element('Holiday')
            date = et.SubElement(holiday, 'Date')
            date.text = holiday_string
            holidays.append(holiday)

        xml_string = et.tostring(holidays)
        return xml_string

    def check_space_input_df_format(self, df: pd.DataFrame):
        '''Method for checking the format of the space input spreadsheet.
        '''
        df_columns =  df.columns
        if df_columns[0] != 'Room/Enclosure' or \
            df_columns[1] != 'Number of occupants' or \
            df_columns[2] != 'Occupant density (m^2/person)' or \
            df_columns[3] != 'Area (m^2)' or \
            df_columns[4] != 'Qty' or \
            df_columns[5] != 'Space Type':
            return False
        else:
            return True

class Building:
    def __init__(self, input_object: Inputs, use_density: bool=False):
        '''
        Instantiate the building object.
        '''
        self.n_spaces = 0
        self.n_occupants = 0
        self.description = f'A building which contains {self.n_spaces} spaces and {self.n_occupants} occupants.'
        self.space_list = []

        self.space_list.append(Space('S0_Outdoor', 'Outdoor')) #Add an outdoor space that is available on all models.

        space_count = 1 #Instantiate space count at 1 since outdoor space is already added
        self.occupant_list = {}
        self.occupant_id_list = []
        for row in input_object.space_input_df.index: #Go through each row in the space input DF
            n_occupants = 0 #Instantiate variable for number of occupants

            space_name = input_object.space_input_df.loc[row, 'Room/Enclosure'] #Get space name
            space_type_input = str(input_object.space_input_df.loc[row, 'Space Type']) #Get space type input
            multiplier = int(input_object.space_input_df.loc[row, 'Qty']) #Get space multiplier input
            
            if space_type_input in input_object.office_space_type_list: #Check if space type is available in list of office space types

                if not use_density: #Use density flag indicates if number of occupants need to be calculated from density and area, or directly read from input
                    n_occupants_input = input_object.space_input_df.loc[row, 'Number of occupants']
                    if math.isnan(n_occupants_input):
                        n_occupants = input_object.space_input_df.loc[row, 'Area (m^2)'] * 1 #Assume occupant density is 1 if entry is not available for office space type
                    else:
                        n_occupants = int(input_object.space_input_df.loc[row, 'Number of occupants'])
                else:
                    occupant_density_input = input_object.space_input_df.loc[row, 'Occupant density (m^2/person)']
                    if math.isnan(occupant_density_input):
                        n_occupants = int(input_object.space_input_df.loc[row, 'Area (m^2)']/1) #Assume occupant density is 1 if entry is not available for office space type
                    else:
                        n_occupants = int(input_object.space_input_df.loc[row, 'Area (m^2)'] / input_object.space_input_df.loc[row, 'Occupant density (m^2/person)'])

                for i in range(multiplier): #Iterate through multiplier value to create that many spaces
                    office_space = OfficeSpace(f'S{space_count}_{space_name}') #Instantiate office space object
                    occ_probabilities = input_object.space_types[space_type_input].occupant_probabilities #Retrieve probability dictionary for various occupant types for that space
                    for occupant_type in list(occ_probabilities.keys()): #Iterate through occupant types for the space type
                        if occupant_type not in input_object.behavior_type_list: #Check if the occupant type has a matching set of columsn in the occupant behavior input.
                            raise Exception(f'Occupant type {occupant_type} in space {space_name} does not have a definition in the behavior input spreadsheet.')
                    office_space.add_occupants_to_office(n_occupants, occ_probabilities) #Add occupant objects to the office space
                    self.occupant_list.update(office_space.occupants_list) # Update master list with occupant list for the space
                    self.occupant_id_list = list(self.occupant_list.keys())
                    self.space_list.append(office_space) #Add space object to list
                    space_count += 1 #Increment number of spaces

            elif space_type_input in input_object.meeting_room_space_type_list: #Check if space type is in list of meeting space types
                for i in range(multiplier):
                    self.space_list.append(MeetingSpace(f'S{space_count}_{space_name}', space_type_input)) #Append meeting space object to list of spaces
                    space_count += 1 #Increment number of spaces
            else:
                for i in range(multiplier):
                    self.space_list.append(Space(f'S{space_count}_{space_name}', 'Other')) #Append an "other" space to list of spaces
                    space_count += 1 #Increment number of spaces
        
        if input_object.sort_flag:
            self.sort_occupant_list(input_object)
        else:
            self.sorted_occupant_id_list = self.occupant_id_list
        self.n_spaces = space_count
        self.n_occupants = len(self.occupant_id_list)

        occupant_info_df = pd.DataFrame(columns=["Occupant name", "Assigned office", "Job type"])
        occupant_list = []
        space_list = []
        job_type_list = []
        for space in self.space_list:
            if type(space) == OfficeSpace:
                for occupant in space.occupant_id_list:
                    space_list.append(space.id)
                    occupant_list.append(occupant)
                    job_type_list.append(space.occupants_list[occupant].movement_behavior_name)
        occupant_info_df['Occupant name'] = occupant_list
        occupant_info_df['Assigned office'] = space_list
        occupant_info_df['Job type'] = job_type_list
        occupant_info_df.to_excel('./occupant_space_dict.xlsx')


    def sort_occupant_list(self, input_object: Inputs):
        self.sorted_occupant_id_list = []
        for sorted_occupant_type in input_object.occupant_sort_order:
            for occupant_id in self.occupant_id_list:
                occupant_type = self.occupant_list[occupant_id].movement_behavior_name
                if occupant_type == sorted_occupant_type:
                    self.sorted_occupant_id_list.append(occupant_id)

    def return_building_xml_string(self, input_object: Inputs):
        '''Return XML string for building object.
        '''
        buildings = et.Element('Buildings')
        building = et.SubElement(buildings, 'Building')
        building.set('ID', 'Building_1')

        description = et.SubElement(building, 'Description')
        description.text = f'A office building which contains {self.n_spaces} spaces and {self.n_occupants} occupants.'
        building_type = et.SubElement(building, 'Type')
        building_type.text = 'Office'
        spaces = et.SubElement(building, 'Spaces')
        spaces.set('ID', 'All_Spaces')

        for space in self.space_list:
            space_xml_string = space.return_xml_string(input_object)
            space_xml = et.fromstring(space_xml_string)
            spaces.append(space_xml)

        xml_string = et.tostring(buildings)
        return xml_string
    
    def return_occupants_xml_string(self):
        '''Return XML string for occupants section.
        '''

        occupants = et.Element('Occupants')

        # for occupant_id in self.occupant_id_list:
        for occupant_id in self.sorted_occupant_id_list:
            occupant_object = self.occupant_list[occupant_id]
            occupant_xml_string = occupant_object.return_xml_string()
            occupant_xml = et.fromstring(occupant_xml_string)
            occupants.append(occupant_xml)

        xml_string = et.tostring(occupants)
        return xml_string

    def return_complete_xml_string(self, input_object: Inputs):
        '''Return complete obXML string.
        '''

        occupant_behavior = et.Element('OccupantBehavior')
        occupant_behavior.set('xmlns:xsi', "http://www.w3.org/2001/XMLSchema-instance")
        occupant_behavior.set('ID', 'OS001')
        occupant_behavior.set('Version', '1.3.2')
        occupant_behavior.set('xsi:noNamespaceSchemaLocation', 'obXML_v1.3.2.xsd')

        buildings_xml_string = self.return_building_xml_string(input_object)
        buildings_xml = et.fromstring(buildings_xml_string)
        occupant_behavior.append(buildings_xml)

        occupants_xml_string = self.return_occupants_xml_string()
        occupants_xml = et.fromstring(occupants_xml_string)
        occupant_behavior.append(occupants_xml)

        behaviors_xml_string = input_object.return_behaviors_section_xml_string()
        behaviors_xml = et.fromstring(behaviors_xml_string)
        occupant_behavior.append(behaviors_xml)

        holidays_xml_string = input_object.return_holidays_section_xml_string()
        holidays_xml = et.fromstring(holidays_xml_string)
        occupant_behavior.append(holidays_xml)

        xml_string = et.tostring(occupant_behavior)
        return xml_string


class Space:
    def __init__(self, name: str = '', type: str = ''):
        '''Instantiate space object.
        '''
        if name == '':
            raise Exception("Blank space name.")
        if type == '':
            raise Exception(f"Incorrect input for space type for space {name}.")

        self.id = name
        self.type = type

    def return_xml_string(self, input_object: Inputs):
        '''Return XML string for space.
        '''
        space = et.Element('Space')
        space.set('ID', self.id)
        type_of_space = et.SubElement(space, 'Type')
        type_of_space.text = self.type

        xml_string = et.tostring(space)
        return xml_string

class OfficeSpace(Space):
    def __init__(self, name: str):
        '''Instantiate office space object.
        '''
        self.occupants_list = []
        super().__init__(name, 'OfficeShared')

    def add_occupants_to_office(self, n_occupants: int, occupant_probabilities: dict):
        '''Determine occupant type and create occupant object for each occupant in the space.
        '''
        if n_occupants == 0:
            raise Exception(f"Incorrect number of occupants input for space {self.name}.")

        job_types = random.choices(list(occupant_probabilities.keys()), list(occupant_probabilities.values()), k= n_occupants) #Determine list of occupant types for the zone based on the occupant type weights.

        self.occupants_list = {}
        self.occupant_id_list = []
        for occ in range(n_occupants): #iterate through each occupant in space
            occ_name = f'{self.id}_{(occ+1):02d}'
            self.occupant_id_list.append(occ_name)
            movement_behavior_name = job_types[occ] #Get the movement behavior type for the occupant
            self.occupants_list[occ_name] = Occupant(occ_name, movement_behavior_name) # Add occupant object to the list of occupants in the space
    
    def return_xml_string(self, input_object: Inputs):
        '''Return XML string for office space.
        '''
        basic_xml_string = super().return_xml_string(input_object)

        office_space = et.fromstring(basic_xml_string)

        for occupant_id in self.occupant_id_list:
            occupant_xml = et.Element('OccupantID')
            occupant_xml.text = occupant_id
            office_space.append(occupant_xml)

        xml_string = et.tostring(office_space)
        return xml_string

class MeetingSpace(Space):
    
    def __init__(self, name: str, meeting_space_type_name: str):
        '''Instantiate meeting space object
        '''
        super().__init__(name, 'MeetingRoom')
        self.meeting_space_type_name = meeting_space_type_name

    def return_xml_string(self, input_object: Inputs):
        '''Return XML string for meeting space.
        '''
        basic_xml_string = super().return_xml_string(input_object)
        
        meeting_space = et.fromstring(basic_xml_string)

        meeting_space_type = input_object.space_types[self.meeting_space_type_name]

        for meeting_event in meeting_space_type.meeting_events:
            meeting_event_xml_string = meeting_event.return_xml_string()
            meeting_event_xml = et.fromstring(meeting_event_xml_string)
            meeting_space.append(meeting_event_xml)

        xml_string = et.tostring(meeting_space)
        return xml_string

class Occupant:
    def __init__(self, name: str, movement_behavior_name: str):
        '''Instantiate occupant object.
        '''
        self.name = name
        self.lifestyle = "Norm"
        self.movement_behavior_name = movement_behavior_name

        self.regular_staff_occupant_types = ['regular staff', 'janitorial', 'cleaning staff', 'maintenance staff', 'recluse', 'social', 'meeting heavy', 'cleaning', 'maintenance', 'meeting participant', 'guest'] + ["occtype_" + str(i) for i in range(271)]  # Occupant behavior types that represent regular staff job type.
        self.admin_occupant_types = ['administrator', 'supervisor']  # Occupant behavior types that represent administrator job type.
        self.researcher_occupant_types = ['researcher', 'scholar', 'guest speaker']  # Occupant behavior types that represent researcher job type.
        self.manager_occupant_types = ['manager', 'executive', 'boss', 'director']  # Occupant behavior types that represent manager job type.
        self.job_type_definitions_sets_dict = {'Regular staff': self.regular_staff_occupant_types,
                                      'Researcher': self.researcher_occupant_types,
                                      'Manager': self.manager_occupant_types,
                                      'Administrator': self.admin_occupant_types} #Dictionary of defined job types and their associated occupant behavior types.

        self.job_type = self.get_job_type_definition(movement_behavior_name) #Get defined job type based on occupant behavior type

    def get_job_type_definition(self, movement_behavior_name: str):
        '''Get job type umbrella term based on movement behavior type name.job type definitions dictionary.
        '''
        found = False
        for key, definition_set in zip(self.job_type_definitions_sets_dict.keys(), self.job_type_definitions_sets_dict.values()): #Cycle through key-value pairs in job type definitions dictionary.
            for definition in definition_set: #Iterate through each definition in definition set
                if definition.lower() in movement_behavior_name.lower(): #Check if the definition term exists in the behavior type name
                    found = True
                    return key #Return job type definition
                
        if not found:
            raise Exception(f"Job name {movement_behavior_name} does not have relevant umbrella term defined in lines 381-385 in occSim_classes.py.")

    def return_xml_string(self):
        '''Return XML string for occupant section.
        '''
        occupant = et.Element('Occupant')
        occupant.set('ID', self.name)
        lifestyle = et.SubElement(occupant, 'LifeStyle')
        lifestyle.text = self.lifestyle
        jobtype = et.SubElement(occupant, 'JobType')
        jobtype.text = self.job_type
        movement_behavior_id = et.SubElement(occupant, 'MovementBehaviorID')
        movement_behavior_id.text = self.movement_behavior_name

        xml_string = et.tostring(occupant)
        return xml_string
        

class OfficeSpaceType:
    def __init__(self, columns: pd.DataFrame):
        '''Instanbtiate office space type object based on column data input.
        '''
        self.name = columns.columns[0]
        self.list_of_occupant_types = []
        self.occupant_probabilities = {}
        for index in columns.index: #Cycle through each row in the space type data
            if index > 0: #Ignore first row which contains occupant density
                if index < len(columns.index): #Check if end of column has been reached
                    if str(columns.iloc[index, 0]) != 'nan': #If end of column is not reached, check if the row has a NaN value, which indicates end of space type values
                        name = str(columns.iloc[index, 0]).replace("Office:", '').replace("occupant percentage", '').replace('-', '').replace("[%]", '').strip() #Get occupant type string from row
                        probability = float(columns.iloc[index, 1]) #Get occupant type probability from row
                        self.list_of_occupant_types.append(name) #Append occupant type to list of occupant types
                        self.occupant_probabilities[name] = probability #Add occupant type name and probility to dict of occupant type probabilities.
                    else:
                        break
                else:
                    break
        if sum(self.occupant_probabilities.values()) != 100: #Check if probabilities for all occupant types sums up to 100.
            raise Exception(f"Incorrect probability values in space type definition for {self.name}.")

class MeetingSpaceType:
    def __init__(self, columns: pd.DataFrame):
        '''Instantiate meeting space type.
        '''
        self.name = columns.columns[0]
        self.meeting_events = []

        i = 0
        end = False #Flag that is set to true when the end of the meeting space type definition is reached. Useful incase there are NAN values at end
        size_of_meeting_events = 10 #Number of rows that are required for each meeting event definition.
        while not end: #Run the loop till the end of definition is reached
            if size_of_meeting_events*i < len(columns.index): #Check if end of complete column is reached
                if str(columns.iloc[size_of_meeting_events*i, 1]) != 'nan': #If end of column is not reached, check if next row has Nan value, which indicates the definition has ended
                    list_of_seasons = [item.strip() for item in columns.iloc[size_of_meeting_events*i, 1].strip().split(',')] #Get list of seasons, which is read in as one single string, and separate it into list of items
                    list_of_days = [item.strip() for item in columns.iloc[size_of_meeting_events*i + 1, 1].strip().split(',')] #Get list of days of week, which is read in as one single string, and separate it into list of items
                    meeting_number_min = int(columns.iloc[size_of_meeting_events*i + 2, 1]) #Read minimum number of meetings in a day
                    meeting_number_max = int(columns.iloc[size_of_meeting_events*i + 3, 1]) #Read maximum number of meetings in a day
                    meeting_attendance_min = int(columns.iloc[size_of_meeting_events*i + 4, 1]) #Read minimum nunmber of attendants at a meeting
                    meeting_attendance_max = int(columns.iloc[size_of_meeting_events*i + 5, 1]) #Read maximum nummber of attendants at a meeting
                    meeting_duration_probabilties = {
                        '30': float(columns.iloc[size_of_meeting_events*i + 6, 1]),
                        '60': float(columns.iloc[size_of_meeting_events*i + 7, 1]),
                        '90': float(columns.iloc[size_of_meeting_events*i + 8, 1]),
                        '120': float(columns.iloc[size_of_meeting_events*i + 9, 1])
                    } #Dictionary of meeting duration probabilities
                    if sum(meeting_duration_probabilties.values()) != 100: #Check if sum of meeting duration probabilities adds up to a 100
                        raise Exception(f"Incorrect meeting duration probability values in space type definition for {self.name}.")
                    self.meeting_events.append(MeetingSpaceType.MeetingEvent(list_of_seasons, list_of_days, meeting_number_min, meeting_number_max, meeting_attendance_min, meeting_attendance_max, meeting_duration_probabilties)) #Create and append a meeting event object

                    i += 1 #Increment the number of meeting events added to meeting space type object.
                else:
                    end = True #Set flag to true to end the while loop at end of definition
            else:
                end = True #Set flag to true to end the while loop at end of definition
    
    class MeetingEvent:
        def __init__(self, list_of_seasons:list, list_of_days:list, meeting_number_min:int, meeting_number_max:int, meeting_attendance_min:int, meeting_attendance_max:int, meeting_duration_probabilties:dict):
            '''Instantiate a meeting event object.
            '''
            self.list_of_seasons = list_of_seasons
            self.list_of_days = list_of_days
            self.meeting_number_min = meeting_number_min
            self.meeting_number_max = meeting_number_max
            self.meeting_attendance_min = meeting_attendance_min
            self.meeting_attendance_max = meeting_attendance_max
            self.meeting_duration_probabilties = meeting_duration_probabilties

        def return_xml_string(self):
            meeting_event = et.Element('MeetingEvent')
            
            for season in self.list_of_seasons:
                season_type = et.Element('SeasonType')
                season_type.text = season
                meeting_event.append(season_type)

            for day in self.list_of_days:
                day_of_week = et.Element('DayofWeek')
                day_of_week.text = day
                meeting_event.append(day_of_week)

            min_occ_number = et.SubElement(meeting_event, 'MinNumOccupantsPerMeeting')
            min_occ_number.text = str(self.meeting_attendance_min)
            max_occ_number = et.SubElement(meeting_event, 'MaxNumOccupantsPerMeeting')
            max_occ_number.text = str(self.meeting_attendance_max)
            min_meet_number = et.SubElement(meeting_event, 'MinNumberOfMeetingsPerDay')
            min_meet_number.text = str(self.meeting_number_min)
            max_meet_number = et.SubElement(meeting_event, 'MaxNumberOfMeetingsPerDay')
            max_meet_number.text = str(self.meeting_number_max)

            for duration in self.meeting_duration_probabilties.keys():
                meeting_duration_prob = et.Element('MeetingDurationProbability')
                meeting_duration = et.SubElement(meeting_duration_prob, 'MeetingDuration')
                meeting_duration.text = f'PT{duration}M'
                probability = et.SubElement(meeting_duration_prob, 'Probability')
                probability.text = str(self.meeting_duration_probabilties[duration]/100)
                meeting_event.append(meeting_duration_prob)

            xml_string = et.tostring(meeting_event)
            return xml_string

class BehaviorType:

    class StatusTransitionEvent:
        def __init__(self, event_type: str, short_term_leaving_time_typical: str, short_term_leaving_time_early: str, short_term_leaving_duration_typical: str = 0, short_term_leaving_duration_minimum: str = 0):
            '''Instantiate a status transition event object.
            '''
            if event_type == 'ShortTermLeaving': #Check if the event type is short-term leaving, which has more parameters to define.
                self.event_type = event_type
                self.short_term_leaving_time_early = short_term_leaving_time_early
                self.short_term_leaving_time_typical = short_term_leaving_time_typical
                self.short_term_leaving_duration_typical = f'PT{short_term_leaving_duration_typical:0>2d}M'
                self.short_term_leaving_duration_minimum = f'PT{short_term_leaving_duration_minimum:0>2d}M'
            else:
                self.event_type = event_type
                self.short_term_leaving_time_early = short_term_leaving_time_early
                self.short_term_leaving_time_typical = short_term_leaving_time_typical

        def return_xml_string(self):
            '''Generate XML section string for status transition event object.
            '''

            status_transition_event = et.Element('StatusTransitionEvent')
            event_type = et.SubElement(status_transition_event, 'EventType')
            event_type.text = self.event_type
            event_occur_model = et.SubElement(status_transition_event, 'EventOccurModel')
            normal_probability_model = et.SubElement(event_occur_model, 'NormalProbabilityModel')
            early_occur_time = et.SubElement(normal_probability_model, 'EarlyOccurTime')
            early_occur_time.text = self.short_term_leaving_time_early
            typical_occur_time = et.SubElement(normal_probability_model, 'TypicalOccurTime')
            typical_occur_time.text = self.short_term_leaving_time_typical

            if self.event_type == 'ShortTermLeaving':
                event_duration = et.SubElement(status_transition_event, 'EventDuration')
                normal_duration_model = et.SubElement(event_duration, 'NormalDurationModel')
                typical_duration = et.SubElement(normal_duration_model, 'TypicalDuration')
                typical_duration.text = self.short_term_leaving_duration_typical
                minimum_duration = et.SubElement(normal_duration_model, 'MinimumDuration')
                minimum_duration.text = self.short_term_leaving_duration_minimum

            xml_string = et.tostring(status_transition_event)
            return xml_string

    class TimeInSpace:
        def __init__(self, space_name: str, percent_time: float, duration_of_stay: int):
            '''Instantiate a time-spent-in-space object.
            '''
            self.space_name = space_name
            self.percent_time = percent_time
            self.duration_of_stay = f'PT{int(duration_of_stay):0>2d}M'

        def return_xml_string(self):
            '''Generate XML section string for space occupancy object.
            '''
            space_occupancy = et.Element('SpaceOccupancy')
            space_category = et.SubElement(space_occupancy, 'SpaceCategory')
            space_category.text = str(self.space_name)
            percent_time_presence = et.SubElement(space_occupancy, 'PercentTimePresence')
            percent_time_presence.text = str(self.percent_time)
            duration = et.SubElement(space_occupancy, 'Duration')
            duration.text = str(self.duration_of_stay)

            xml_string = et.tostring(space_occupancy)
            return xml_string

    def __init__(self, columns: pd.DataFrame):
        '''Instantiate an occupant behavior type object.
        '''
        self.name = columns.columns[0]
        self.list_of_seasons = [item.strip() for item in columns.iloc[0, 1].strip().split(',')] #Get list of seasons, which is read in as one single string, and separate it into list of items
        self.list_of_days = [item.strip() for item in columns.iloc[1, 1].strip().split(',')] #Get list of days of week, which is read in as one single string, and separate it into list of items

        self.status_transition_events = []
        try:
            arrival_time_typical = datetime.datetime.strptime(str(columns.iloc[2, 1]), '%H:%M:%S').time() #Read a time string from DF, which automatically creates a datetime object.
        except:
            arrival_time_typical = datetime.datetime.strptime(columns.iloc[2, 1], '%H:%M:%S').time() #Read a time string from DF, which automatically creates a datetime object.
        
        arrival_time_variation = datetime.timedelta(minutes = columns.iloc[3, 1]) #Read variation in arrival time to get a timedelta object
        arrival_time_early = (datetime.datetime.combine(datetime.date(2022, 1, 1), arrival_time_typical) - arrival_time_variation).strftime('%H:%M:%S') #Calculate earliest arrival time and convert to time string
        self.status_transition_events.append(BehaviorType.StatusTransitionEvent('Arrival', arrival_time_typical.strftime('%H:%M:%S'), arrival_time_early)) #Create a status transition event for arrival with only string inputs
        
        try:
            departure_time_typical = datetime.datetime.strptime(str(columns.iloc[4, 1]), '%H:%M:%S').time() #Read a time string from DF, which automatically creates a datetime object.
        except:
            departure_time_typical = datetime.datetime.strptime(columns.iloc[4, 1], '%H:%M:%S').time() #Read a time string from DF, which automatically creates a datetime object.

        departure_time_variation = datetime.timedelta(minutes = columns.iloc[5, 1]) #Read variation in departure time to get a timedelta object
        departure_time_early = (datetime.datetime.combine(datetime.date(2022, 1, 1), departure_time_typical) - departure_time_variation).strftime('%H:%M:%S') #Calculate earliest departure time and convert to time string
        self.status_transition_events.append(BehaviorType.StatusTransitionEvent('Departure', departure_time_typical.strftime('%H:%M:%S'), departure_time_early)) #Create a status transition event for departure with only string inputs
        
        space_list = ['OwnOffice', 'OtherOffice', 'MeetingRoom', 'AuxRoom', 'Outdoor'] #List of spaces in which an occupant can spend time as per behavior type
        self.random_movement_events = [] #List of random movement event objects
        start_of_space_values = 6 #Variable indicating random movement events start on row 5 of input columns
        for i, space in enumerate(space_list): #Iterate through each space and it's index in list of spaces
            percent_time = float(columns.iloc[(2*i + start_of_space_values), 1]) #Read percent of time spent in each space
            duration_of_stay = float(columns.iloc[(2*i + start_of_space_values + 1), 1]) #Read typical time duration spent in each space
            self.random_movement_events.append(BehaviorType.TimeInSpace(space, percent_time, duration_of_stay)) #Create a time-spent-in-space object and append it to list of random movement event objects.

        end_of_space_values = 15 #14th row is last row containing values for random movement events
        end = False #Flag used to identify that end of behavior type definition has been reached.
        i = 0 #Variable to count number of short term leaving events added to the behavior type object
        size_of_status_transition_events = 4 #Number of input rows for each short term leaving event
        while not end: #Run loop till end of definition is reached
            if (size_of_status_transition_events*i + end_of_space_values + 1) < len(columns.index): #Identify end of column has been reached
                if (str(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 1), 1]) != 'nan'): #If end of column is not reached, check if row has NaN value, indicating end of definition
                    
                    try:
                        short_term_leaving_time_typical = datetime.datetime.strptime(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 1), 1], '%H:%M:%S').time() #Read typical short term leaving time from DF, which automatically creates a dtaetime object
                    except:
                        short_term_leaving_time_typical = datetime.datetime.strptime(str(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 1), 1]), '%H:%M:%S').time() #Read typical short term leaving time from DF, which automatically creates a dtaetime object

                    short_term_leaving_time_early_delta = datetime.timedelta(minutes = float(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 2), 1])) #Read variation in short term leaving time to datetime object
                    short_term_leaving_time_early = (datetime.datetime.combine(datetime.date(2022, 1, 1), short_term_leaving_time_typical) - short_term_leaving_time_early_delta).time() #Calculate early short term leaving time
                    short_term_leaving_duration_typical = datetime.timedelta(minutes = float(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 3), 1])) #Read typical short term leaving duration to timedelta object
                    short_term_leaving_duration_minimum_delta = datetime.timedelta(minutes = float(columns.iloc[(size_of_status_transition_events*i + end_of_space_values + 4), 1])) #Read variation in short term leaving duration to timedelta object
                    short_term_leaving_duration_minimum = short_term_leaving_duration_typical - short_term_leaving_duration_minimum_delta #Calculate minimum duration of short term leaving
                    self.status_transition_events.append(BehaviorType.StatusTransitionEvent('ShortTermLeaving', short_term_leaving_time_typical.strftime('%H:%M:%S'), short_term_leaving_time_early.strftime('%H:%M:%S'), \
                        int(short_term_leaving_duration_typical.seconds/60), int(short_term_leaving_duration_minimum.seconds/60))) #Create and attach a status transition event for short term leaving to the list of status transition events, using only time strings and duration minutes integers as inputs

                    i += 1 #Increment number of short term leaving events by 1
                else:
                    end = True #Set flag to true to end while loop
            else:
                end = True #Set flag to true to end while loop

    def return_xml_string(self):
        '''Generate XML section string for movement behavior object.
        '''
        movement_behavior = et.Element('MovementBehavior')
        movement_behavior.set('ID', self.name)

        for season in self.list_of_seasons:
            season_type = et.SubElement(movement_behavior, 'SeasonType')
            season_type.text = season

        for day in self.list_of_days:
            day_of_week = et.SubElement(movement_behavior, 'DayofWeek')
            day_of_week.text = day
        
        random_movement_event = et.SubElement(movement_behavior, 'RandomMovementEvent')

        for event in self.random_movement_events:
            event_xml_string = event.return_xml_string()
            event_element = et.fromstring(event_xml_string)
            random_movement_event.append(event_element)

        for event in self.status_transition_events:
            event_xml_string = event.return_xml_string()
            status_transition_event = et.fromstring(event_xml_string)
            movement_behavior.append(status_transition_event)

        xml_string = et.tostring(movement_behavior)
        return xml_string
        