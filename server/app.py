import configparser
from flask import Flask, jsonify, request, session, send_file
from werkzeug.utils import secure_filename
from flask_cors import CORS
import os
import pandas as pd
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import time
from io import BytesIO
import zipfile
from libraries.abort_utils import abort_event
from libraries.utils import (Items, TimeUnit, ProductionOrder, ExecutionPlan, Machines, BoM, 
    BoMItem, DataHandler)
from libraries.main_handler import executePandS, processExtrusionInput

INPUT_FOLDER = 'Planos'
ALLOWED_EXTENSIONS = {'xlsx'}
CLEANUP_INTERVAL = 30  # Run the temp cleanup every 30 minutes
TEMP_FILES_LIFETIME = 3600  # Delete temp files older than 1 hour (3600 seconds)

# Read the configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Extract database configuration
db_server = config['Database']['db_server']
db_username = config['Database']['db_username']
db_password = config['Database']['db_password']
secret_key = config['Secret Key']['secret_key']

# All existing criteria and specific user data
all_criteria, user_data = None, {}

# Instantiate the app
app = Flask(__name__)
app.config.update(UPLOAD_FOLDER=None, TEMP_FOLDER=None, SECRET_KEY=secret_key)

# Load data from both databases
for db_name in ["COFACTORY_PT", "COFACTORY_GR"]:
    connection_string = f'DRIVER={{SQL Server}};SERVER={db_server};DATABASE={db_name};UID={db_username};PWD={db_password};'
    DataHandler.readDBData(connection_string, db_name)

# Enable CORS
CORS(app, resources={r'/*': {'origins': '*'}}, supports_credentials=True)

# Create a SQL Server connection function
def get_chart_data(database):
    exec_plan_instances = ExecutionPlan.GR_instances if database == "COFACTORY_GR" else ExecutionPlan.PT_instances
    time_unit_instances = TimeUnit.GR_instances if database == "COFACTORY_GR" else TimeUnit.PT_instances
    machine_instances = Machines.GR_instances if database == "COFACTORY_GR" else Machines.PT_instances

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
        for ep in exec_plan_instances
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
                for ep in tu.ExecutionPlans  
            ]
        }
        for tu in time_unit_instances
    ]

    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in machine_instances
    ]
        
    return exec_plans, time_units, machines

def get_new_chart_data(dataHandler):
    exec_plan_instances = ExecutionPlan.GR_instances if dataHandler.Database == "COFACTORY_GR" else ExecutionPlan.PT_instances
    machine_instances = Machines.GR_instances if dataHandler.Database == "COFACTORY_GR" else Machines.PT_instances
    
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
        for ep in exec_plan_instances
    ]
    
    new_exec_plans = [
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
        for ep in dataHandler.ExecutionPlans
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
        for tu in dataHandler.TimeUnits
    ]

    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in machine_instances
    ]
        
    return exec_plans, new_exec_plans, time_units, machines

@app.route('/selectBranch', methods=['POST'])
async def select_branch():
    # Get the selected branch
    data = request.json
    selected_branch = data.get('branch')
    user_id = data.get('userId')
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID não fornecido.'}), 400

    # Save the user ID in the session
    session['user_id'] = user_id

    # Update the input and temp folder paths for the specific user
    app.config['UPLOAD_FOLDER'] = os.path.join(INPUT_FOLDER, user_id)
    app.config['TEMP_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')

    # Create the input and temp folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
    
    user_data[user_id] = {
        "input_data": None,
        "input_file": None,
    }
    
    if selected_branch != "COFACTORY_PT" and selected_branch != "COFACTORY_GR":
        return jsonify({'status': 'error', 'message': 'Unidade de produção inválida.'}), 400
    
    connection_string = f'DRIVER={{SQL Server}};SERVER={db_server};DATABASE={selected_branch};UID={db_username};PWD={db_password};'
    # Generate the connection string, which contains the server, chosen database, and the username and password to access it
    user_data[user_id]["input_data"] = DataHandler(selected_branch, connection_string)
    
    # Get the desired data from the chosen database
    user_data[user_id]["input_data"].setupData()
    
    return jsonify({
        'status': 'success', 
        'message': f'Base de dados {selected_branch} selecionada.'
    })

@app.route('/getChartData', methods=['GET'])
def get_all_data():
    response_object = {'status': 'success'}
    
    user_id = session.get('user_id')
    dataHandler = user_data[user_id]["input_data"]
    
    # Get the necessary data to populate the Gantt Chart
    exec_plans, time_units, machines = get_chart_data(dataHandler.Database)
    
    # Populate the response object with the execution plans, time units, and machine data
    response_object['exec_plans'] = exec_plans
    response_object['time_units'] = time_units
    response_object['machines'] = machines
    return jsonify(response_object)

@app.route('/getNewChartData', methods=['GET'])
def get_results_data():
    user_id = session.get('user_id')
    dataHandler = user_data[user_id]["input_data"]
    response_object = {'status': 'success'}
    
    # Get the newly created data (algorithm results) to populate the new Gantt Chart
    exec_plans, new_exec_plans, time_units, machines = get_new_chart_data(dataHandler)
    response_object['exec_plans'] = exec_plans
    response_object['new_exec_plans'] = new_exec_plans
    response_object['time_units'] = time_units
    response_object['machines'] = machines
    return jsonify(response_object)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_temp_folder():
    """Delete temp files older than FILE_LIFETIME seconds."""
    now = time.time()
    for filename in os.listdir(app.config['TEMP_FOLDER']):
        file_path = os.path.join(app.config['TEMP_FOLDER'], filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > TEMP_FILES_LIFETIME:
                os.remove(file_path)
                print(f"Deleted old temp file: {file_path}")

def validate_file(file_path):
    # Expected column types for the input file
    EXPECTED_COLUMNS = {
        "Item": str,        
        "Quantity": int,       
        "StartDate": "datetime64[ns]",        
        "Priority": int,   
    }
    
    try:
        df = pd.read_excel(file_path, engine="openpyxl")

        # Check if all required data columns exist        
        if set(df.columns) != set(EXPECTED_COLUMNS.keys()):
            return False
        
        df = df.infer_objects() 
        
        # Check if each column has the correct data type
        for column, expected_type in EXPECTED_COLUMNS.items():
            if expected_type == int:
                if not pd.api.types.is_integer_dtype(df[column]):
                    return False
            elif expected_type == str:
                if not pd.api.types.is_string_dtype(df[column]):
                    return False
            elif expected_type == "datetime64[ns]":
                if not pd.api.types.is_datetime64_any_dtype(df[column]):
                    return False

        return True
    except Exception as e:
        print(e)
        return False
    
@app.route('/uploadInputFile', methods=['POST'])
def upload_file():    
    file = request.files['file']
    user_id = session.get('user_id', None)
    
    # Validate if a file was selected
    if file.filename == '':
        return jsonify({'message': 'Nenhum ficheiro selecionado.'}), 400
    
    # Validate the file format and process the file if valid
    if file and allowed_file(file.filename):
        # Secure the filename, cleanign any special chars
        filename = secure_filename(file.filename)
        
        # Store the file temporarily
        temp_file_path = os.path.join(app.config['TEMP_FOLDER'], filename) 
        file.save(temp_file_path)
        
        # Validate the input file data
        is_valid = validate_file(temp_file_path)
        if not is_valid:
            return jsonify({'message': 'Ficheiro inválido, tente outra vez.'}), 400
        
        user_data[user_id]["input_file"] = temp_file_path
        dataHandler = user_data[user_id]["input_data"]
        dataHandler.CurrentTime = None
        
        """# Store the file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file)  # Save file content
            temp_file_path = temp_file.name  # Store the path"""
        
        """# Extract the original file name without the extension
        original_name, extension = os.path.splitext(file.filename)
        
        new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{original_name}_*.{extension.strip('.')}")

        # Find existing files with a similar name in the upload folder
        existing_files = glob.glob(new_file_path)
        
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
        new_file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        input_file = new_file_path

        # Ensure the upload folder exists, creating it if not, and save the file to the server
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(new_file_path)
        
        is_valid = validate_file(new_file_path)
        if not is_valid:
            os.remove(new_file_path)
            return jsonify({'message': 'Ficheiro inválido.'}), 400

        # Reset the current time, since we introduce a new input file 
        current_time = None"""

        # Return success response with the file path
        return jsonify({'message': 'Ficheiro lido e guardado com sucesso.', 'file_path': temp_file_path}), 200

    # Return error response if the file format is invalid
    return jsonify({'message': 'O formato do ficheiro é inválido.'}), 400

@app.route('/deleteInputFile', methods=['POST'])
def delete_file():     
    user_id = session.get('user_id', None)
    
    if user_id in user_data and "input_file" in user_data[user_id]:
        os.remove(user_data[user_id]["input_file"])
        
    return jsonify({'status': 'success'}), 200

@app.route('/criteria', methods=['POST'])
def process_criteria():
    global all_criteria
    data = request.json
    selected_criteria = data.get('selectedCriteria')
    criteria = data.get('allCriteria')
    
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    all_criteria = criteria
    
    # Parse the criteria, from string to int
    parsed_criteria = {int(k): v for k, v in selected_criteria.items()}

    # Save the criteria in the dataHandler of the respective user
    dataHandler.Criteria = parsed_criteria
    print(parsed_criteria)

    return jsonify({'message': 'Critérios processados com sucesso.', 'criteria': selected_criteria}), 200

@app.route('/machines', methods=['GET'])
def get_machines():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    machine_instances = Machines.GR_instances if dataHandler.Database == "COFACTORY_GR" else Machines.PT_instances
    
    machines = [
        {
            'name': machine.MachineCode,
            'input': machine.Input,
            'output': machine.Output,
            'RT': machine.RunningTimeFactor
        }
        for machine in machine_instances
    ]
    
    processes = ['ROD0', 'MDW0', 'BUN0']
            
    return jsonify({'status': 'success', 'machines': machines, 'processes': processes})

@app.route('/BoMs', methods=['GET'])
def get_BoMs():
    user_id = session.get('user_id', None)
    
    # Get the BoM's from the products in the inputted production orders
    item_BoMs = DataHandler.getInputBoMs(user_data[user_id]["input_file"])

    return jsonify({'status': 'success', 'item_BoMs': item_BoMs})

@app.route('/removeMachines', methods=['POST'])
def remove_machines():
    machines_to_remove = request.json
    
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    machine_instances = Machines.GR_instances if dataHandler.Database == "COFACTORY_GR" else Machines.PT_instances

    # Remove the chosen machines, by deactivating them
    for machine_name in machines_to_remove:
        machine = next((m for m in machine_instances if machine_name == m.MachineCode), None)
        if machine:
            machine.IsActive = False
    
    return jsonify({"message": "BoM's removidas com sucesso."}), 200 # A success message is returned, if the machines are removed successfully.

@app.route('/removeBoMs', methods=['POST'])
def remove_boms():
    boms_to_remove = request.json
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    
    # Add to the algorithm criteria the BoM's that should disregarded
    dataHandler.Criteria[5] = boms_to_remove

    return jsonify({"message": "Máquinas removidas com sucesso."}), 200 # A success message is returned, if the BoM's are removed successfully.

@app.route('/createData', methods=['POST'])
def create_data():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    
    if dataHandler.CurrentTime is None:
        dataHandler.CurrentTime = datetime.now()
        
    # Clear the user-specific data instances
    dataHandler.clearNewDataInstances()
    
    # Process input file
    no_routings, no_bom = processExtrusionInput(dataHandler, user_data[user_id]["input_file"])
    
    return jsonify({
        "message": "Os dados foram criados com sucesso.",
        "no_routings": no_routings,
        "no_bom": no_bom,
    }), 200

@app.route('/runAlgorithm', methods=['POST'])
def run_algorithm():
    # If the COFACTORY_PT database is selected, the PT_Settings configuration will enable the execution of the ROD process.
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    
    PT_Settings = True if dataHandler.Database == "COFACTORY_PT" else False

    # Run the algorithm, periodically checking for the abort flag.
    abort_event.clear()
    success = executePandS(dataHandler, PT_Settings)

    if success:
        return jsonify({"message": "Algoritmo executado com sucesso."}), 200 # A success message is returned, if the algorithm is executed successfully.
    else:
        return jsonify({"message": "A execução do algoritmo foi abortada."}), 200 # A error message is returned, if the algorithm is unexpectedly aborted.

@app.route('/abortAlgorithm', methods=['POST'])
def abort_algorithm():
    # Endpoint to set the abort flag.
    abort_event.set()
    return jsonify({"message": "Algoritmo interrompido."}), 200

@app.route('/saveResults', methods=['POST'])
def save_results():
    user_id = session.get('user_id', None)
    if not user_id or user_id not in user_data:
        return jsonify({"error": "Utilizador não autenticado."}), 403
    
    dataHandler = user_data[user_id]["input_data"]
    current_time = int(dataHandler.CurrentTime.strftime("%d%m%Y%H%M%S"))
    
    plano_id = f"{current_time}_{user_id}"
    
    # Move file from temporary storage to permanent location
    input_file = user_data[user_id].get("input_file")
    if input_file and os.path.exists(input_file):
        plan_folder = os.path.join(app.config['UPLOAD_FOLDER'], plano_id)
        os.makedirs(plan_folder, exist_ok=True)
        final_path = os.path.join(plan_folder, f"Plano_{current_time}.xlsx")
        os.rename(input_file, final_path)
        user_data[user_id]["input_file"] = None
    else:
        return jsonify({"error": "Ficheiro não encontrado."}), 404    
        
    # Organize the created plan in two Excel files, and write them to the plan folder
    PT_Settings = True if dataHandler.Database == "COFACTORY_PT" else False
    PO_Excel = dataHandler.writeExcelData(PT_Settings, True)
    detailed_PO_Excel = dataHandler.writeExcelData(PT_Settings, False)
    
    # File names and their content
    file_names = {"OUTPUT_MetalPlan.xlsx": PO_Excel, "OUTPUT_MetalPlanDetailed.xlsx": detailed_PO_Excel}
    
    # Write the plan Excel files to their respective plan folder
    for filename, file_obj in file_names.items():
        file_path = os.path.join(plan_folder, filename)
        with open(file_path, "wb") as f:
            f.write(file_obj.getvalue())
    
    dataHandler.writeDBData(plano_id)
    
    activated_criteria = [all_criteria[idx] for idx, activated in dataHandler.Criteria.items() if activated]
    with open(os.path.join(plan_folder, "criteria.txt"), "w") as f:
        f.writelines(f"{criteria}\n" for criteria in activated_criteria)
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, file_obj in file_names.items():
            zip_file.writestr(filename, file_obj.getvalue())
            
    zip_buffer.seek(0)

    if dataHandler.Database == "COFACTORY_GR":
        ExecutionPlan.GR_instances.extend(dataHandler.ExecutionPlans)
        TimeUnit.GR_instances.extend(dataHandler.TimeUnits)
    else: 
        ExecutionPlan.PT_instances.extend(dataHandler.ExecutionPlans)
        TimeUnit.PT_instances.extend(dataHandler.TimeUnits)
        
    #return jsonify({"message": "Resultados guardados com sucesso."}), 200
    return send_file(zip_buffer, as_attachment=True, download_name='OUTPUT_Plans.zip', mimetype='application/zip')

@app.route('/getPlanHistory', methods=['POST'])
def plan_history():
    # Get all plan folders in the user directory with their modification times
    folders = [
        (folder, os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], folder)))
        for folder in os.listdir(app.config['UPLOAD_FOLDER'])
        if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], folder))
    ]
    
    folders.sort(key=lambda x: x[1], reverse=True)

    for folder, time in folders:
        print(folder, time) 
        
    return jsonify({"message": "Resultados guardados com sucesso."}), 200
   
if __name__ == '__main__':
    # Start the temp cleanup scheduler before running the app
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_temp_folder, 'interval', minutes=CLEANUP_INTERVAL)
    scheduler.start()
    
    try:
        app.run(host= '0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        scheduler.shutdown() # The scheduler is properly shut down if the app stops
        