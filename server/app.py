from flask import Flask, jsonify, request, session, send_file, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
import os
import pandas as pd
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
import time
from io import BytesIO
import zipfile
from dotenv import load_dotenv
from libraries.abort_utils import abort_event
from libraries.utils import (TimeUnit, ExecutionPlan, Machines, DataHandler)
from libraries.main_handler import executePandS, processExtrusionInput

# Load the .env file with environment variables
load_dotenv('.env')

INPUT_FOLDER = os.environ.get('STORAGE_PATH')
ALLOWED_EXTENSIONS = {'xlsx'}
CLEANUP_INTERVAL = 30  # Run the temp cleanup every 30 minutes
TEMP_FILES_LIFETIME = 3600  # Delete temp files older than 1 hour (3600 seconds)

# All existing criteria and specific user data
all_criteria, user_data = None, {}

# Instantiate the app
app = Flask(__name__)

# Set configuration from environment variables
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY'),
    HOST=os.environ.get('HOST', '0.0.0.0'),
    PORT=os.environ.get('PORT', '5001'),
    URL=os.environ.get('URL', 'http://localhost'),
)

# Create thread pool and tracking dictionaries
executor = ThreadPoolExecutor(max_workers=5)
running_algorithms = {}

# Load data from both databases
connection_strings = {
    "COFACTORY_PT": f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={os.environ.get("COFPT_DATABASE_SERVER")};'
                    f'DATABASE={os.environ.get("COFPT_DATABASE_NAME")};UID={os.environ.get("COFPT_DATABASE_USERNAME")};'
                    f'PWD={os.environ.get("COFPT_DATABASE_PASSWORD")};'
                    f'TrustServerCertificate=yes;',
    
    "COFACTORY_GR": f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={os.environ.get("COFGR_DATABASE_SERVER")};'
                    f'DATABASE={os.environ.get("COFGR_DATABASE_NAME")};UID={os.environ.get("COFGR_DATABASE_USERNAME")};'
                    f'PWD={os.environ.get("COFGR_DATABASE_PASSWORD")};'
                    f'TrustServerCertificate=yes;'
}

for db_name, connection_string in connection_strings.items():
    DataHandler.readDBData(connection_string, db_name)

# Enable CORS
CORS(app, resources={r'/*': {'origins': '*'}}, supports_credentials=True)

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

def get_new_chart_data(dataHandler, planoId = None):
    exec_plan_instances = ExecutionPlan.GR_instances if dataHandler.Database == "COFACTORY_GR" else ExecutionPlan.PT_instances
    machine_instances = Machines.GR_instances if dataHandler.Database == "COFACTORY_GR" else Machines.PT_instances
    
    # Helper function to format execution plans consistently
    def format_exec_plan(ep):
        return {
            'id': ep.id,
            'itemRoot': ep.ItemRoot.Name if ep.ItemRoot is not None else None,
            'itemRelated': ep.ItemRelated.Name,
            'quantity': ep.Quantity,
            'ST': ep.ST,
            'CoT': ep.CoT,
            'machine': ep.Machine,
            'orderIncrement': ep.ItemRelated.OrderIncrement,
        }
    
    # Filter by planoId if it exists, otherwise use all plans
    filtered_plans = [ep for ep in exec_plan_instances if ep.PlanoId != planoId] if planoId else [ep for ep in exec_plan_instances]
    
    # Format all execution plans
    exec_plans = [format_exec_plan(ep) for ep in filtered_plans]
    
    # Filter by planoId if it exists, otherwise use all plans
    filtered_plans = [ep for ep in exec_plan_instances if ep.PlanoId == planoId] if planoId else dataHandler.ExecutionPlans

    # Format plan specific execution plans
    new_exec_plans = [format_exec_plan(ep) for ep in filtered_plans]

    # Format time units
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

    # Format machines
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
    
    global user_data
    
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID não fornecido.'}), 400

    # Save the user ID in the session
    session['user_id'] = user_id

    # Update the input and temp folder paths for the specific user (session)
    branch_folder = os.path.join(INPUT_FOLDER, selected_branch)
    upload_folder = os.path.join(branch_folder, user_id)
    temp_folder = os.path.join(upload_folder, 'temp')
    
    # Store paths in session for request context
    session['upload_folder'] = upload_folder
    session['temp_folder'] = temp_folder

    # Create the folders
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(temp_folder, exist_ok=True)
    
    if selected_branch != "COFACTORY_PT" and selected_branch != "COFACTORY_GR":
        return jsonify({'status': 'error', 'message': 'Unidade de produção inválida.'}), 400
    
    # Get the connection string, which contains the server, chosen database, and the username and password to access it
    connection_string = connection_strings[selected_branch]
    
    # Store data in the global dictionary instead of session
    user_data[user_id] = {
        "input_data": DataHandler(selected_branch, connection_string),
        "temp_folder": temp_folder, # Store the temp folder path in a separate structure aswell for background tasks
    }
    
    # Set up the data handler
    user_data[user_id]['input_data'].setupData() 
        
    return jsonify({
        'status': 'success', 
        'message': f'Base de dados {selected_branch} selecionada.'
    })

@app.route('/getChartData', methods=['GET'])
def get_all_data():
    response_object = {'status': 'success'}
    
    user_id = session.get('user_id')
    dataHandler = user_data[user_id]['input_data']
    
    # Get the necessary data to populate the Gantt Chart
    exec_plans, time_units, machines = get_chart_data(dataHandler.Database)
    
    # Populate the response object with the execution plans, time units, and machine data
    response_object['exec_plans'] = exec_plans
    response_object['time_units'] = time_units
    response_object['machines'] = machines
    return jsonify(response_object)

@app.route('/getNewChartData', methods=['GET'])
def get_results_data():
    plano_id = request.args.get('planoId')
    
    user_id = session.get('user_id')
    dataHandler = user_data[user_id]['input_data']
    response_object = {'status': 'success'}
    
    # Get the newly created data (algorithm results) to populate the new Gantt Chart
    exec_plans, new_exec_plans, time_units, machines = get_new_chart_data(dataHandler, plano_id)
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
    
    for _, user_info in user_data.items():
        if "temp_folder" in user_info and user_info["temp_folder"]:
            for filename in os.listdir(user_info['temp_folder']):
                file_path = os.path.join(user_info['temp_folder'], filename)
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
        temp_file_path = os.path.join(session['temp_folder'], filename) 
        file.save(temp_file_path)
        
        # Validate the input file data
        is_valid = validate_file(temp_file_path)
        if not is_valid:
            os.remove(temp_file_path)
            return jsonify({'message': 'Ficheiro inválido, tente outra vez.'}), 400
        
        session['input_file'] = temp_file_path
        dataHandler = user_data[user_id]['input_data']
        dataHandler.CurrentTime = None

        # Return success response with the file path
        return jsonify({'message': 'Ficheiro lido e guardado com sucesso.', 'file_path': temp_file_path}), 200

    # Return error response if the file format is invalid
    return jsonify({'message': 'O formato do ficheiro é inválido.'}), 400

@app.route('/deleteInputFile', methods=['POST'])
def delete_file():     
    user_id = session.get('user_id', None)
    input_file = session.get('input_file', None)
    
    if user_id and input_file:
        os.remove(session['input_file'])
        
    return jsonify({'status': 'success'}), 200

@app.route('/criteria', methods=['POST'])
def process_criteria():
    global all_criteria
    data = request.json
    selected_criteria = data.get('selectedCriteria')
    criteria = data.get('allCriteria')
    
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']    
    all_criteria = criteria
    
    # Parse the criteria, from string to int
    parsed_criteria = {int(k): v for k, v in selected_criteria.items()}

    # Save the criteria in the dataHandler of the respective user
    dataHandler.Criteria = parsed_criteria
    print(parsed_criteria)

    return jsonify({'status': 'success', 'criteria': selected_criteria}), 200

@app.route('/machines', methods=['GET'])
def get_machines():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']
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
    
    processes = ['ROD', 'MDW', 'BUN']
            
    return jsonify({'status': 'success', 'machines': machines, 'processes': processes})

@app.route('/BoMs', methods=['GET'])
def get_BoMs():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']
    
    # Get the BoM's from the products in the inputted production orders
    item_BoMs = dataHandler.getInputBoMs(session['input_file'])

    return jsonify({'status': 'success', 'item_BoMs': item_BoMs})

@app.route('/removeMachines', methods=['POST'])
def remove_machines():
    machines_to_remove = request.json
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']
    
    # Eensure all previous deactivated machines are reactivated
    for machine in dataHandler.Machines:
        if not machine.IsActive:
            machine.IsActive = True

    # Remove the chosen machines, by deactivating them
    for machine_name in machines_to_remove:
        machine = next((m for m in dataHandler.Machines if machine_name == m.MachineCode), None)
        if machine:
            machine.IsActive = False
            
    # Add to the user's session the machines that should be deactivated    
    session['machines_to_remove'] = machines_to_remove
    
    return jsonify({'status': 'success'}), 200 # A success message is returned, if the machines are removed successfully.

@app.route('/removeBoMs', methods=['POST'])
def remove_boms():
    boms_to_remove = request.json
    
    # Add to the user's session the BoM's that should disregarded
    session['BoMs_to_remove'] = boms_to_remove

    return jsonify({'status': 'success'}), 200 # A success message is returned, if the BoM's are removed successfully.

@app.route('/createData', methods=['POST'])
def create_data():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']
    
    if dataHandler.CurrentTime is None:
        dataHandler.CurrentTime = datetime.now()
        
    # Add to the algorithm criteria the machines and BoM's that should disregarded
    if 'machines_to_remove' in session:
        dataHandler.Criteria[0] = session['machines_to_remove']

    if 'BoMs_to_remove' in session:
        dataHandler.Criteria[5] = session['BoMs_to_remove'] 
    
    # Clear the user-specific data instances
    dataHandler.clearNewDataInstances()
    
    # Process input file
    no_routings, no_bom = processExtrusionInput(dataHandler, session['input_file'])
    
    return jsonify({
        'status': 'success',
        'no_routings': no_routings,
        'no_bom': no_bom,
    }), 200
    
def run_algorithm_in_thread(user_id, dataHandler, PT_Settings):
    """Run the algorithm in a separate thread"""
    try:
        # Clear any abort flag
        abort_event.clear()
        
        # Run the algorithm
        success = executePandS(dataHandler, PT_Settings)
        
        # Update the algorithm status
        running_algorithms[user_id]["status"] = "completed"
        running_algorithms[user_id]["success"] = success
        running_algorithms[user_id]["message"] = "Algoritmo executado com sucesso." if success else "A execução do algoritmo foi abortada."
    except Exception as e:
        import traceback
        # Update status with error information
        running_algorithms[user_id]["status"] = "error"
        running_algorithms[user_id]["success"] = False
        running_algorithms[user_id]["message"] = str(e)
        running_algorithms[user_id]["traceback"] = traceback.format_exc()
    finally:
        # Keep the result for a while so the client can query it
        def cleanup():
            time.sleep(300)  # Keep results for 5 minutes
            if user_id in running_algorithms:
                del running_algorithms[user_id]
                
        threading.Thread(target=cleanup).start()

@app.route('/runAlgorithm', methods=['POST'])
def run_algorithm():
    # Get the user ID from the session
    user_id = session.get('user_id') or request.args.get('user_id')
    
    # Check if the algorithm is already running for this user
    if user_id in running_algorithms and running_algorithms[user_id]["status"] == "running":
        return jsonify({
            'status': 'already_running',
            'message': 'O algoritmo já está em execução para este utilizador.'
        }), 400
        
    # Check if the thread pool is full
    if executor._work_queue.qsize() >= executor._max_workers:
        return jsonify({
            'status': 'pool_full',
            'message': 'A execução do algoritmo está em capacidade máxima. Por favor, tente novamente mais tarde.'
        }), 503  
    
    dataHandler = user_data[user_id]['input_data']
    
    # Check if PT_Settings should be enabled
    PT_Settings = True if dataHandler.Database == "COFACTORY_PT" else False
    
    # Initialize the algorithm status
    running_algorithms[user_id] = {
        "id": str(uuid.uuid4()),
        "status": "running",
        "success": None,
        "message": "Algoritmo em execução.",
        "start_time": time.time()
    }
    
    # Submit the algorithm to the thread pool
    executor.submit(run_algorithm_in_thread, user_id, dataHandler, PT_Settings)
    
    return jsonify({
        'status': 'success',
        'message': 'Iniciada a execução do algoritmo.',
        'task_id': running_algorithms[user_id]["id"]
    }), 202 

@app.route('/algorithmStatus', methods=['GET'])
def algorithm_status():
    user_id = session.get('user_id') or request.args.get('user_id')
    
    if not user_id:
        return jsonify({
            'status': 'error', 
            'message': 'User ID não encontrado. Por favor atualize a página.'
        }), 400
    
    # Log for debugging
    print(f"Status check for user_id: {user_id}, Active algorithms: {list(running_algorithms.keys())}")
    
    # Check if there's a task for this user
    if user_id not in running_algorithms:
        return jsonify({'status': 'not_running', 'message': 'Este utilizador não tem nenhum algoritmo em execução.'}), 200 
    
    # Return the algorithm status
    status = running_algorithms[user_id]
    
    # Check if the algorithm has finished or crashed
    if status["status"] in ["completed", "error", "aborted"]:
        # Remove it after a short delay to allow the client to receive the result
        def delayed_removal():
            time.sleep(5)  
            if user_id in running_algorithms:
                del running_algorithms[user_id]
                print(f"Removed finished algorithm for user {user_id}")
        
        threading.Thread(target=delayed_removal).start()
    
    return jsonify(status)

@app.route('/abortAlgorithm', methods=['POST'])
def abort_algorithm():
    user_id = session.get('user_id')
    
    # Check if there's an algorithm running for this user
    if user_id in running_algorithms and running_algorithms[user_id]["status"] == "running":
        # Set the abort flag
        abort_event.set()
        
        # Update the algorithm status
        running_algorithms[user_id]["status"] = "aborted"
        running_algorithms[user_id]["message"] = "Algorithm was aborted by user"
        
        return jsonify({'status': 'success', 'message': 'Algoritmo abortado.'}), 200
    
    # If we get here, either there's no algorithm for this user or it's already completed
    return jsonify({'status': 'not_found', 'message': 'Não foi encontrado nenhum algoritmo em execução.'}), 404

@app.route('/saveResults', methods=['POST'])
def save_results():
    user_id = session.get('user_id', None)    
    dataHandler = user_data[user_id]['input_data']
    
    # Get the minimum ST value from all execution plans
    min_ST = min(plan.ST for plan in dataHandler.ExecutionPlans)
    
    formatted_ST = int(min_ST.strftime("%d%m%Y%H%M%S"))
    
    plano_id = f"{formatted_ST}_{user_id}"
    
    # Move file from temporary storage to permanent location
    input_file = session.get('input_file', None)  
    if input_file and os.path.exists(input_file):
        plan_folder = os.path.join(session['upload_folder'], plano_id)
        os.makedirs(plan_folder, exist_ok=True)
        final_path = os.path.join(plan_folder, f"Plano_{formatted_ST}.xlsx")
        os.rename(input_file, final_path)
        session['input_file'] = None
    else:
        return jsonify({'status': 'not_found', "message": "Ficheiro não encontrado."}), 404    
        
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
    
    with open(os.path.join(plan_folder, "criteria.txt"), "w") as f:
        selected_criteria = []

        for idx, criteria in dataHandler.Criteria.items():
            if criteria:
                # Add the basic criterion name
                text = all_criteria[idx]
                
                # For removing machines or BoMs, add details
                if idx == 0 or idx == 5:
                    text += f": {criteria}"

                selected_criteria.append(text)

        # Join all criteria with commas
        f.write(", \n".join(selected_criteria))
            
    """activated_criteria = [all_criteria[idx] for idx, activated in dataHandler.Criteria.items() if activated]
    
    with open(os.path.join(plan_folder, "criteria.txt"), "w") as f:
        for idx, criteria in enumerate(activated_criteria):
            if idx == len(activated_criteria) - 1: # Check if it's the last element
                f.write(f"{criteria}") # Don't add a comma after the last element
            else:
                f.write(f"{criteria}, \n") # Add a comma after each element except the last one"""
    
    zip_file_path = os.path.join(plan_folder, "OUTPUT_Plans.zip")

    # Create a ZIP archive for OUTPUT files
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename, file_obj in file_names.items():
            zipf.writestr(filename, file_obj.getvalue())
            
    # Read the ZIP file into memory for download
    with open(zip_file_path, "rb") as f:
        zip_buffer = BytesIO(f.read())
    zip_buffer.seek(0)

    if dataHandler.Database == "COFACTORY_GR":
        ExecutionPlan.GR_instances.extend(dataHandler.ExecutionPlans)
        TimeUnit.GR_instances.extend(dataHandler.TimeUnits)
    else: 
        ExecutionPlan.PT_instances.extend(dataHandler.ExecutionPlans)
        TimeUnit.PT_instances.extend(dataHandler.TimeUnits)
        
    #return jsonify({"message": "Resultados guardados com sucesso."}), 200
    return send_file(zip_buffer, as_attachment=True, download_name='OUTPUT_Plans.zip', mimetype='application/zip')

def get_ep_by_plano_id(database, plano_id):
    exec_plan_instances = ExecutionPlan.GR_instances if database == "COFACTORY_GR" else ExecutionPlan.PT_instances

    filtered_instances = [ep for ep in exec_plan_instances if ep.PlanoId == plano_id]

    if not filtered_instances:
        return []  # Return an empty list if no matching execution plans are found

    min_ST = min(ep.ST for ep in filtered_instances)
    max_CoT = max(ep.CoT for ep in filtered_instances)

    return [min_ST, max_CoT]

@app.route('/getPlanHistory', methods=['POST'])
def plan_history():
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]['input_data']
    
    plan_history_list = []  # Store the final structured response
    
    branch_folder = os.path.join(INPUT_FOLDER, dataHandler.Database)
    
    user_folders = [
        folder for folder in os.listdir(branch_folder)
        if os.path.isdir(os.path.join(branch_folder, folder))
    ]
    
    for user_folder in user_folders:
        user_folder_path = os.path.join(branch_folder, user_folder)
        
        # Get all plan folders in the user directory with their modification times
        plan_folders = [
            (folder, os.path.getmtime(os.path.join(user_folder_path, folder)))
            for folder in os.listdir(user_folder_path)
            if os.path.isdir(os.path.join(user_folder_path, folder)) and folder != "temp"
        ]
        
        # Sort folders by modification time (latest first)
        plan_folders.sort(key=lambda x: x[1], reverse=True)
        
        # Plan folders that dont exist in the DB should be removed
        folders_to_remove = []
    
        for path_folder, _ in plan_folders:
            plan_folder_path = os.path.join(user_folder_path, path_folder)
            
            # Prepare lists for input files, output files, and criteria content
            input_files = []
            output_files = []
            criteria_contents = []
            PORT = app.config["PORT"]
            URL = app.config["URL"]
            
            # Add the zipped file with the plans data to output files
            zip_file_path = os.path.join(plan_folder_path, "OUTPUT_Plans.zip")
            if os.path.exists(zip_file_path):
                output_files.append(f"{URL}:{PORT}/download/{path_folder}/OUTPUT_Plans.zip")
    
            for file in os.listdir(plan_folder_path):
                file_path = os.path.join(plan_folder_path, file)
                if os.path.isfile(file_path):
                    file_url = f"{URL}:{PORT}/download/{path_folder}/{file}"
                    
                    # Categorize files
                    if file.startswith("Plano"): # Input file used to create the plan
                        input_files.append(file_url)
                    elif file.startswith("criteria"): # File with chosen criteria
                        try:
                            with open(file_path, "r", encoding="utf-8") as criteria_file:
                                for line in criteria_file:
                                    criteria_contents.append(line.strip())
                        except UnicodeDecodeError:
                            with open(file_path, "r", encoding="latin-1") as criteria_file:  # Try fallback encoding
                                for line in criteria_file:
                                    criteria_contents.append(line.strip())
            
            # Get the plan's ST and CoT 
            ST_and_CoT = get_ep_by_plano_id(dataHandler.Database, path_folder)
            
            if not ST_and_CoT:
                folders_to_remove.append(plan_folder_path)
                continue
            
            # Append the structured data to the response list
            plan_history_list.append({
                "user_id": user_folder,
                "folder": path_folder,
                "inputFiles": input_files,
                "outputFiles": output_files,
                "ST": ST_and_CoT[0],
                "CoT": ST_and_CoT[1],
                "criteria": criteria_contents
            })
            
    # Remove folders after completing all processing
    for folder_path in folders_to_remove:
        try:
            os.remove(folder_path)
            print(f"Removed folder: {folder_path}")
        except Exception as e:
            print(f"Error removing folder {folder_path}: {e}")
            
    return jsonify(plan_history_list), 200

@app.route('/download/<folder_name>/<filename>', methods=['GET'])
def download_file(folder_name, filename):
    """Serves files from the user's plan history folder."""
    plan_folder = os.path.join(session['upload_folder'], folder_name)
    
    if not os.path.exists(os.path.join(plan_folder, filename)):
        return jsonify({"message": "Ficheiro não encontrado."}), 404

    return send_from_directory(plan_folder, filename, as_attachment=True)
   
if __name__ == '__main__':
    # Start the temp cleanup scheduler before running the app
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup_temp_folder, 'interval', minutes=CLEANUP_INTERVAL)
    scheduler.start()
    
    try:
        app.run(host=app.config["HOST"], port=app.config["PORT"], debug=False)
    except KeyboardInterrupt:
        scheduler.shutdown() # The scheduler is properly shut down if the app stops
        