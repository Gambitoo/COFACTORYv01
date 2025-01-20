import configparser
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import glob
from datetime import datetime
from libraries.abort_utils import abort_event
from libraries.utils import (TimeUnit, ProductionOrder, ExecutionPlan, Machines, 
    InputData)
from libraries.main_handler import executePandS, processExtrusionInput
import logging
logging.basicConfig(level=logging.DEBUG)

INPUT_FOLDER = 'Planos'
ALLOWED_EXTENSIONS = {'xlsx'}

# Read the configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Extract database configuration
current_time = datetime.now()
db_server = config['Database']['db_server']
db_username = config['Database']['db_username']
db_password = config['Database']['db_password']
db_database = None

input_file = None
all_criteria = None
current_time = None

# Instantiate the app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = INPUT_FOLDER

# Enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})

# Create a SQL Server connection function
def get_chart_data():
    exec_plans = [
        {
            'id': ep.id,
            'itemRoot': ep.ItemRoot.Name if ep.ItemRoot is not None else None,
            'itemRelated': ep.ItemRelated.Name,
            'quantity': ep.Quantity,
            'ST': ep.ST,
            'CoT': ep.CoT,
            'machine': ep.Machine,
            'orderIncrement': ep.ItemRelated.OrderIncrement,
        }
        for ep in ExecutionPlan.instances
    ]

    time_units = [
        {
            'id': tu.id,
            'machine': tu.Machine,
            'ST': tu.ST,
            'CoT': tu.CoT,
            'execution_plans': [
                {
                    'id': ep.id,
                    'itemRoot': ep.ItemRoot.Name if ep.ItemRoot is not None else None,
                    'itemRelated': ep.ItemRelated.Name,
                    'quantity': ep.Quantity,
                    'ST': ep.ST,
                    'CoT': ep.CoT,
                    'machine': ep.Machine,
                    'orderIncrement': ep.ItemRelated.OrderIncrement,
                }
                for ep in tu.ExecutionPlans  # Access the ExecutionPlans associated with each TimeUnit
            ]
        }
        for tu in TimeUnit.instances
    ]

    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in Machines.instances
    ]
    
    return exec_plans, time_units, machines

def get_new_chart_data():
    exec_plans = [
        {
            'id': ep.id,
            'itemRoot': ep.ItemRoot.Name if ep.ItemRoot is not None else None,
            'itemRelated': ep.ItemRelated.Name,
            'quantity': ep.Quantity,
            'ST': ep.ST,
            'CoT': ep.CoT,
            'machine': ep.Machine,
            'orderIncrement': ep.ItemRelated.OrderIncrement,
        }
        for ep in ExecutionPlan.new_instances
    ]

    time_units = [
        {
            'id': tu.id,
            'machine': tu.Machine,
            'ST': tu.ST,
            'CoT': tu.CoT,
            'execution_plans': [
                {
                    'id': ep.id,
                    'itemRoot': ep.ItemRoot.Name if ep.ItemRoot is not None else None,
                    'itemRelated': ep.ItemRelated.Name,
                    'quantity': ep.Quantity,
                    'ST': ep.ST,
                    'CoT': ep.CoT,
                    'machine': ep.Machine,
                    'orderIncrement': ep.ItemRelated.OrderIncrement,
                }
                for ep in tu.ExecutionPlans  # Access the ExecutionPlans associated with each TimeUnit
            ]
        }
        for tu in TimeUnit.new_instances
    ]

    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in Machines.instances
    ]
    
    return exec_plans, time_units, machines

@app.route('/selectBranch', methods=['POST'])
async def select_branch():
    # Get the selected branch
    data = request.json
    select_branch = data.get('branch')
    
    # Clear the cached data
    ExecutionPlan.clear_instances()
    Machines.clear_instances()
    TimeUnit.clear_instances()
    
    
    if select_branch != "COFACTORY_PT" and select_branch != "COFACTORY_GR":
        return jsonify({'status': 'error', 'message': 'Unidade de produção inválida.'}), 400

    global connection_string, inputData, db_database
    db_database = select_branch
    
    # Generate the connection string, which contains the server, chosen database, and the username and password to access it
    connection_string = f'DRIVER={{SQL Server}};SERVER={db_server};DATABASE={select_branch};UID={db_username};PWD={db_password};'
    inputData = InputData(select_branch, connection_string)
    
    # Get the desired data from the chosen database
    inputData.readDBData()
    return jsonify({
        'status': 'success', 
        'message': f'Base de dados {select_branch} selecionada.'
    })

@app.route('/getChartData', methods=['GET'])
def get_all_data():
    response_object = {'status': 'success'}
    
    # Get the necessary data to populate the Gantt Chart
    exec_plans, time_units, machines = get_chart_data()
    
    # Populate the response object with the execution plans, time units, and machine data
    response_object['exec_plans'] = exec_plans
    response_object['time_units'] = time_units
    response_object['machines'] = machines
    return jsonify(response_object)

@app.route('/getNewChartData', methods=['GET'])
def get_results_data():
    response_object = {'status': 'success'}
    
    # Get the newly created data (algorithm results) to populate the new Gantt Chart
    exec_plans, time_units, machines = get_new_chart_data()
    response_object['exec_plans'] = exec_plans
    response_object['time_units'] = time_units
    response_object['machines'] = machines
    return jsonify(response_object)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadFile', methods=['POST'])
def upload_file():
    global current_time 

    file = request.files['file']
    # Validate if a file was selected
    if file.filename == '':
        return jsonify({'message': 'Nenhum ficheiro selecionado.'}), 400
    
    # Validate the file format and process the file if valid
    if file and allowed_file(file.filename):
        # Extract the original file name without the extension
        original_name, extension = os.path.splitext(file.filename)

        # Find existing files with a similar name in the upload folder
        existing_files = glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], f"{original_name}_*.{extension.strip('.')}"))

        # Extract the unique number from the existing files and determine the next ID
        ID = 1
        if existing_files:
            # Extract numeric suffixes to determine the next ID
            IDs = [
                int(os.path.basename(file).split('_')[-1].split('.')[0])
                for file in existing_files if file.split('_')[-1].split('.')[0].isdigit()
            ]
            if IDs:
                ID = max(IDs) + 1

        # Generate a new unique filename
        new_filename = f"{original_name}_{ID}{extension}"
        global input_file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        input_file = file_path

        # Ensure the upload folder exists, creating it if not, and save the file to the server
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(file_path)

        # Reset the current time, since we introduce a new input file 
        current_time = None

        # Return success response with the file path
        return jsonify({'message': 'Ficheiro lido e guardado com sucesso.', 'file_path': file_path}), 200

    # Return error response if the file format is invalid
    return jsonify({'message': 'O formato do ficheiro é inválido.'}), 400

@app.route('/criteria', methods=['POST'])
def process_criteria():
    # Receive criteria
    criteria = request.json  
    
    # Parse the criteria, from string to int
    parsed_criteria = {int(k): v for k, v in criteria.items()}

    # Save the criteria globally
    global all_criteria
    all_criteria = parsed_criteria
    print(all_criteria)

    return jsonify({'message': 'Critérios processados com sucesso.', 'criteria': criteria}), 200

@app.route('/machines', methods=['GET'])
def get_machines():
    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in Machines.instances
    ]
    return jsonify({'status': 'success', 'machines': machines})

@app.route('/BoMs', methods=['GET'])
def get_BoMs():
    # Get the BoM's from the products in the inputted production orders
    item_BoMs = InputData.getInputBoMs(input_file)

    return jsonify({'status': 'success', 'item_BoMs': item_BoMs})

@app.route('/removeMachines', methods=['POST'])
def remove_machines():
    data = request.json
    machines_to_remove = data.get('machines', [])

    # Remove the chosen machines, by deactivating them
    for machine_name in machines_to_remove:
        machine = next((m for m in Machines.instances if machine_name == m.MachineCode), None)
        if machine:
            machine.IsActive = False
    
    return jsonify({"message": "BoM's removidas com sucesso."}), 200 # A success message is returned, if the machines are removed successfully.

@app.route('/removeBoMs', methods=['POST'])
def remove_boms():
    data = request.json
    
    # Add to the algorithm criteria the BoM's that should disregarded
    boms_to_remove = data.get('BoMs')
    all_criteria[5] = boms_to_remove

    return jsonify({"message": "Máquinas removidas com sucesso."}), 200 # A success message is returned, if the BoM's are removed successfully.

@app.route('/createData', methods=['POST'])
def create_data():
    global all_criteria, current_time
    
    if current_time is None:
        current_time = datetime.now()
    
    inputData.Criteria = all_criteria
    inputData.CurrentTime = current_time
    TimeUnit.clear_new_instances()
    ExecutionPlan.clear_new_instances()
    ProductionOrder.clear_instances()
    no_routings, no_bom = processExtrusionInput(inputData, input_file)

    return jsonify({
        "message": "Os dados a serem utilizados no algoritmo foram criados com sucesso.",
        "no_routings": no_routings,
        "no_bom": no_bom,
    }), 200

@app.route('/runAlgorithm', methods=['POST'])
def run_algorithm():
    # If the COFACTORY_PT database is selected, the PT_Settings configuration will enable the execution of the ROD process.
    PT_Settings = True if db_database == "COFACTORY_PT" else False

    # Run the algorithm, periodically checking for the abort flag.
    abort_event.clear()
    success = executePandS(inputData, PT_Settings)

    if success:
        return jsonify({"message": "Algoritmo executado com sucesso."}), 200 # A success message is returned, if the algorithm is executed successfully.
    else:
        return jsonify({"message": "A execução do algoritmo foi abortada."}), 200 # A error message is returned, if the algorithm is unexpectedly aborted.

@app.route('/abortAlgorithm', methods=['POST'])
def abort_algorithm():
    """Endpoint to set the abort flag."""
    abort_event.set()
    return jsonify({"message": "Algoritmo interrompido."}), 200

@app.route('/saveResults', methods=['POST'])
def save_results():
    PT_Settings = True if db_database == "COFACTORY_PT" else False
    inputData.writeExcelData(PT_Settings)
    inputData.writeDBData()

    ExecutionPlan.instances.extend(ExecutionPlan.new_instances)
    TimeUnit.instances.extend(TimeUnit.new_instances)

    return jsonify({"message": "Resultados guardados com sucesso."}), 200
    
if __name__ == '__main__':
    app.run(app, port=5001, debug=False)