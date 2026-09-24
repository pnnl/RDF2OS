import sys, os
import occSim_classes_SPARQL
import xml.etree.ElementTree as et
import subprocess
import time
import json
from config import config

timer = occSim_classes_SPARQL.Timer()
timer.start_time = time.time()

direc_run_OOS = config.get('supporting_files') + '\\'
os.chdir(direc_run_OOS)
sys.path.append(direc_run_OOS)


def generate_occupant_behavior_simulation_xml(input_filename: str, output_xml_name: str):
    input_object = occSim_classes_SPARQL.Inputs(input_filename)
    timer.read_input_time = time.time() - timer.start_time
    building_object = occSim_classes_SPARQL.Building(input_object)
    timer.build_python_object_time = (time.time() - timer.start_time) - timer.read_input_time
    complete_xml_string = building_object.return_complete_xml_string(input_object)
    timer.build_xml_time = (time.time() - timer.start_time) - timer.build_python_object_time
    with open(output_xml_name, mode='w', encoding='utf-8') as out_file:
        et.canonicalize(complete_xml_string, out=out_file)


def run_occSim_FMU(input_xml: str, output_string: str):
    fmu_path = config.get('fmu_executable')
    obcosim_xml = config.get('obcosim_xml')

    subprocess.check_output([fmu_path, input_xml, output_string, obcosim_xml])

    timer.run_simulation_time = (time.time() - timer.start_time) - timer.build_xml_time