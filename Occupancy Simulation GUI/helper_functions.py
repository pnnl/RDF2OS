

from rdflib import ConjunctiveGraph
import pandas as pd
import numpy as np
import sys, time
from config import config

#%% 
class Helper:
      
    def kwH_to_GJ(self, data):
      data = data * .0036
      return data
    
    def days2D(self, data): #288 timeslots, 365 days
      data = np.reshape(data,[int(len(data)/365),365], order = 'F')
      return data
    
    def days_to_weeks(self, data):
      weeks = np.zeros((np.shape(data)[0],52))
      intvls = list(range(0,52*7,7))
      for i in range(len(intvls)-1):
        weeks[:,i] = np.sum(data[:, intvls[i]:intvls[i+1]], axis = 1)      
      return weeks
        
    def group_by_day(self, data):
        data = self.days2D(data)
        days = {}
        for d in range(7):
            days[d] = data[:, d::7]
        return days
    
    def avg_day(self, data): ## group by timeslot
        data = self.days2D(data)
        avg_day = np.mean(data, axis = 1)
        return avg_day
    
    def avg_week_by_day(self, data): ## group by timeslot
        data = self.days2D(data)
        avg_week_days = np.zeros((np.shape(data)[0],7))
        for d in range(7):
            avg_week_days[:,d] = np.mean(data[:, d::7], axis = 1)            
        avg_week_days = np.ndarray.flatten(avg_week_days, 'F')
        return avg_week_days
    
    def sum_day(self, data): ## group by timeslot
        data = self.days2D(data)
        sum_day = np.sum(data, axis = 1)
        return sum_day
    
    def sum_week_by_day(self, data): ## group by timeslot
        data = self.days2D(data)
        sum_week_days = np.zeros((np.shape(data)[0],7))
        for d in range(7):
            sum_week_days[:,d] = np.sum(data[:, d::7], axis = 1)            
        sum_week_days = np.ndarray.flatten(sum_week_days, 'F')
        return sum_week_days
    
        
    def daily_total(self, data): ## group by timeslot
        data = self.days2D(data)
        daily_total = np.sum(data, axis = 0)
        return daily_total
#%%
class Occupancy:
    def __init__(self):
        filedir = r'Supporting_Files'
        self.occSim_data = pd.read_csv(filedir + '/OOS/results_sorted/occSim.csv')  
        # check for (and delete) blank final column -- error from offline occ sim 
        if np.sum(self.occSim_data[list(self.occSim_data.keys())[-1]]) == 0:
            self.occSim_data = self.occSim_data.drop(columns=self.occSim_data.columns[-1], axis = 1)
            
        # replace generic occSim roomnames with room numbers from semantic model
        self.query_data = pd.read_csv(filedir + '/OOS/results_sorted/query_results.csv')
        self.mapping_num = self.query_data['?number']
        self.cols = list(self.occSim_data.columns)
        self.cols[2:-1] = self.mapping_num.copy()
        self.occSim_data.columns = self.cols.copy()

    def date_time(self):
        date_time = self.occSim_data['Time']
        lbls_time = [ dt.split(' ') for dt in date_time ]
        
        dates = [dt[1] for dt in lbls_time]; 
        times = [dt[2] for dt in lbls_time];
    
        return dates, times   
    
    def occCount(self):
        occCount = self.occSim_data
        occCount['Date'] = self.date_time()[0]
        occCount['Time'] = self.date_time()[1]     
        return occCount
    
    def occStatus(self):
        occStatus = self.occCount().copy()
        temp = np.array(occStatus.iloc[:,2:-1]).astype(bool).astype(int)
        occStatus.iloc[:,2:-1] = temp
        return occStatus

    def workdays(self):
      workdays = np.array(self.occStatus()['Whole building'])
      workdays = Helper().days2D(workdays)
      workdays = np.sum(workdays, axis = 0) > 0
      
      return workdays

#%%
class SPARQL:
    def __init__(self):
        try:
            self.sparql = ConjunctiveGraph(store='Oxigraph')
            self.sparql.parse(config.get('building_ttl'), format='ttl')
            self.sparql.parse(config.get('ontology_ttl'), format='ttl')
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize SPARQL graph:\n"
                f"{str(e)}\n\n"
                f"Check that these files exist:\n"
                f"  building_ttl: {config.get('building_ttl')}\n"
                f"  ontology_ttl: {config.get('ontology_ttl')}"
            )

    def run_query(self, query):
        results = self.sparql.query(query, use_store_provided=True)
        return pd.DataFrame(results, columns=[v.toPython() for v in results.vars])


#%%
class HVAC:
    def query_hvac_zones(self):
        query = """
            PREFIX s223: <http://data.ashrae.org/standard223#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
             
            SELECT ?z2 ?roomname ?number ?L
            WHERE {GRAPH ?graph
               {?z a s223:Zone.
                ?z s223:hasDomain s223:Domain-HVAC.
                ?z s223:hasProperty ?z1.
                ?z1 s223:hasValue ?z2.
                ?X a s223:Zone.
                ?z s223:hasDomain s223:Domain-HVAC.
                ?Y a s223:DomainSpace.
                ?Y s223:hasDomain s223:Domain-HVAC.
                ?z s223:hasDomainSpace ?Y.
               #?A rdfs:subClassOf* s223:PhysicalSpace.
                ?A s223:encloses ?Y.
                ?L a s223:OccupantMotionSensor.
                ?L s223:hasPhysicalLocation ?A.
                ?A rdfs:label ?roomname.
                ?A s223:hasProperty ?roomnumber. 
                ?roomnumber a s223:Property. 
                ?roomnumber s223:hasValue ?number.
               
                
            }} GROUP BY ?z2 ?roomname ?number ?L
            """
            
        PD = SPARQL().run_query(query)       
        
        #% remove stairwells and hallways from queried rooms
        idx = []
        for i in range(len(PD['?roomname'])):
            if PD['?roomname'].iloc[i].toPython() == 'Hallway' or PD['?roomname'].iloc[i].toPython() == 'Stairwell':
                idx.append(i)                
        PD = PD.drop(idx)

        
        #% group all rooms belonging to individual hvac zones
        hvac_zones_rooms = {}
        hvac_zones_sensors = {}
        for z in PD['?z2'].unique():
            TMP = PD.loc[PD['?z2'] == z]
            TMP = TMP.sort_values(by = ['?number'])
                       
            # hvac_zones_rooms[z] = list(TMP['?number'])
            
            temp = []
            temp2 = []
            for i in range(len(TMP['?number'])):
                # tmp = str(TMP['?L'].iloc[i]).split('/')[-1]
                # tmp = tmp + ' (Room ' + str(TMP['?number'].iloc[i]) + ')'
                tmp = 'Room ' + str(TMP['?number'].iloc[i])
                temp2.append(tmp)
                temp.append(str(TMP['?number'].iloc[i]))
            
            hvac_zones_sensors[z] = temp2
            hvac_zones_rooms[z] = temp
            
                   
        return hvac_zones_rooms, hvac_zones_sensors
    
    def link_HVAC_occLS(self):
        occStatus = Occupancy().occStatus()
        hvac_zones, hvac_sensors = self.query_hvac_zones()
        
        HVAC_occLS = {}
        for z in hvac_zones.keys():
            rooms = hvac_zones[z]
            HVAC_occLS[z] = occStatus[['Step', 'Date', 'Time'] + rooms]
            
        return HVAC_occLS
            

#%%
# hvac_zones = HVAC().query_hvac_zones()

# for i in range(len(hvac_zones)):
#     print(i, list(hvac_zones.values())[i])