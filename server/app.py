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
from libraries.utils import (Items, TimeUnit, ProductionOrder, ExecutionPlan, Machines, BoM, 
    BoMItem, DataHandler)
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
    UPLOAD_FOLDER=None, 
    TEMP_FOLDER=None,
    HOST=os.environ.get('HOST', '0.0.0.0'),
    PORT=os.environ.get('PORT', '5001')
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
    
    global user_data
    
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
    
    connection_string = connection_strings[selected_branch]
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
            os.remove(temp_file_path)
            return jsonify({'message': 'Ficheiro inválido, tente outra vez.'}), 400
        
        user_data[user_id]["input_file"] = temp_file_path
        dataHandler = user_data[user_id]["input_data"]
        dataHandler.CurrentTime = None

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

    return jsonify({'status': 'success', 'criteria': selected_criteria}), 200

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
    dataHandler = user_data[user_id]["input_data"]
    
    # Get the BoM's from the products in the inputted production orders
    item_BoMs = dataHandler.getInputBoMs(user_data[user_id]["input_file"])

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
    
    return jsonify({'status': 'success'}), 200 # A success message is returned, if the machines are removed successfully.

@app.route('/removeBoMs', methods=['POST'])
def remove_boms():
    boms_to_remove = request.json
    user_id = session.get('user_id', None)
    dataHandler = user_data[user_id]["input_data"]
    
    # Add to the algorithm criteria the BoM's that should disregarded
    dataHandler.Criteria[5] = boms_to_remove

    return jsonify({'status': 'success'}), 200 # A success message is returned, if the BoM's are removed successfully.

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
    user_id = session.get('user_id')
    
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
    
    dataHandler = user_data[user_id]["input_data"]
    
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
    # Get the user ID from the session
    user_id = session.get('user_id')
    
    # Check if there's a task for this user
    if user_id not in running_algorithms:
        return jsonify({'status': 'not_found', 'message': 'Este utilizador não tem nenhum algoritmo em execução.'}), 404
    
    # Return the algorithm status
    status = running_algorithms[user_id]
    
    return jsonify(status)

@app.route('/abortAlgorithm', methods=['POST'])
def abort_algorithm():
    # Get the user ID from the session
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
    
    activated_criteria = [all_criteria[idx] for idx, activated in dataHandler.Criteria.items() if activated]
    with open(os.path.join(plan_folder, "criteria.txt"), "w") as f:
        for idx, criteria in enumerate(activated_criteria):
            if idx == len(activated_criteria) - 1: # Check if it's the last element
                f.write(f"{criteria}") # Don't add a comma after the last element
            else:
                f.write(f"{criteria}, ") # Add a comma after each element except the last one
    
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
    dataHandler = user_data[user_id]["input_data"]
    
    plan_history_list = []  # Store the final structured response
    
    user_folders = [
        folder for folder in os.listdir(INPUT_FOLDER)
        if os.path.isdir(os.path.join(INPUT_FOLDER, folder))
    ]
    
    for user_folder in user_folders:
        user_folder_path = os.path.join(INPUT_FOLDER, user_folder)
        
        # Get all plan folders in the user directory with their modification times
        plan_folders = [
            (folder, os.path.getmtime(os.path.join(user_folder_path, folder)))
            for folder in os.listdir(user_folder_path)
            if os.path.isdir(os.path.join(user_folder_path, folder)) and folder != "temp"
        ]
        
        # Sort folders by modification time (latest first)
        plan_folders.sort(key=lambda x: x[1], reverse=True)
    
        for path_folder, _ in plan_folders:
            plan_folder_path = os.path.join(user_folder_path, path_folder)
            
            # Prepare lists for input files, output files, and criteria content
            input_files = []
            output_files = []
            criteria_contents = []
            
            # Add the zipped file with the plans data to output files
            zip_file_path = os.path.join(plan_folder_path, "OUTPUT_Plans.zip")
            if os.path.exists(zip_file_path):
                output_files.append(f"http://localhost:5001/download/{path_folder}/OUTPUT_Plans.zip")
    
            for file in os.listdir(plan_folder_path):
                file_path = os.path.join(plan_folder_path, file)
                
                if os.path.isfile(file_path):
                    file_url = f"http://localhost:5001/download/{path_folder}/{file}"
                    
                    # Categorize files
                    if file.startswith("Plano"): # Input file used to create the plan
                        input_files.append(file_url)
                    elif file.startswith("criteria"): # File with chosen criteria
                        try:
                            with open(file_path, "r", encoding="utf-8") as criteria_file:
                                criteria_contents.append(criteria_file.read())
                        except UnicodeDecodeError:
                            with open(file_path, "r", encoding="latin-1") as criteria_file:  # Try fallback encoding
                                criteria_contents.append(criteria_file.read())
            
            # Get the plan's ST and CoT 
            ST_and_CoT = get_ep_by_plano_id(dataHandler.Database, path_folder)
            
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
            
    return jsonify(plan_history_list), 200

@app.route('/download/<folder_name>/<filename>', methods=['GET'])
def download_file(folder_name, filename):
    """Serves files from the user's plan history folder."""
    plan_folder = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    
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
        