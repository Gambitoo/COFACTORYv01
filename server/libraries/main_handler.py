import time as tm
from openpyxl import load_workbook
import time as tm
from .abort_utils import abort_event
from .utils import (ProductionOrder, Items, ExecutionPlan)
from .algorithms import (RODPandS, TrefPandS, TorcPandS)

def processExtrusionInput(inputData, file_name):
    no_routings, no_bom = None, []
    Extrusion_Input = load_workbook(file_name)
    Extrusion_Input_Active = Extrusion_Input.active
    for row in Extrusion_Input_Active.iter_rows(min_row=2, values_only=True):
        product_name, qty, due_date, weight = row[:4]
        item = Items.get_Item(product_name)
        if item:
            prod_qty = float(inputData.checkStock(product_name, qty) if inputData.Criteria[3] else qty)
            if prod_qty != 0:
                prod_order = ProductionOrder(item, prod_qty, due_date, weight)
                no_routings = inputData.createExecPlans(item, prod_order)
        else:
            no_bom.append(product_name)

    if inputData.Criteria[5]:
        plans_to_exclude = []
        
        print(inputData.Criteria)
        # Iterate over each root Item and its corresponding deactivated BoMs
        for item_root, BoMs_to_deactivate in inputData.Criteria[5].items():
            plans_by_bom_id = {}
            for exec_plan in ExecutionPlan.new_instances:
                if exec_plan.ItemRoot and exec_plan.ItemRoot.Name == item_root:
                    # Organize the execution plans by BoMId for this root Item
                    plans_by_bom_id.setdefault(exec_plan.BoMId, []).append(exec_plan)

            # Now process each BoM for this root Item
            for _, exec_plans in plans_by_bom_id.items():
                # Check if all related Items with the same BoMid belong to one of the deactivated BoMs
                if all(any(exec_plan.ItemRelated.Name in BoMs for BoMs in BoMs_to_deactivate) for exec_plan in
                       exec_plans):
                    # Add all the execution plans belonging to the deactivated BoM to plans_to_exclude
                    plans_to_exclude.extend(exec_plan.id for exec_plan in exec_plans)

        # Remove the execution plans by their id
        for ep_id in plans_to_exclude:
            ExecutionPlan.remove_by_id(ep_id)

    return no_routings, no_bom

def executePandS(inputData, PT_Settings):
    """Execute Planning and Scheduling with abort functionality."""
    try:
        if abort_event.is_set():
            print("Execution aborted before starting.")
            return False  # Early abort

        print("A calcular...\n")
        st = tm.time()

        # Step 1: Tref Planning
        if abort_event.is_set():
            print("Execution aborted during Tref calculation.")
            return False

        st_Tref = tm.time()
        Tref = TrefPandS(InputData=inputData)
        Tref.Planning()  # Ensure Tref.Planning() checks for abort periodically

        execution_time_ROD = 0
        if PT_Settings:
            # Step 2: ROD Planning and Scheduling
            if abort_event.is_set():
                print("Execution aborted during ROD Planning.")
                return False

            inputData.createRemainingExecPlans(PT_Settings)
            st_ROD = tm.time()
            ROD = RODPandS(InputData=inputData)

            ROD.Planning()  # Ensure ROD.Planning() checks for abort periodically
            if abort_event.is_set():
                print("Execution aborted during ROD Scheduling.")
                return False

            ROD.Scheduling()  # Ensure ROD.Scheduling() checks for abort periodically
            et_ROD = tm.time()
            execution_time_ROD = et_ROD - st_ROD

        # Step 3: Tref Scheduling
        if abort_event.is_set():
            print("Execution aborted during Tref Scheduling.")
            return False

        Tref.Scheduling(PT_Settings)  # Ensure Tref.Scheduling() checks for abort periodically
        et_Tref = tm.time()
        execution_time_Tref = (et_Tref - st_Tref) - execution_time_ROD

        # Step 4: Torc
        if abort_event.is_set():
            print("Execution aborted during Torc calculation.")
            return False

        st_Torc = tm.time()
        TorcPandS(InputData=inputData)  # Ensure TorcPandS() checks for abort periodically
        et_Torc = tm.time()
        execution_time_Torc = et_Torc - st_Torc

        # Finalize
        et = tm.time()
        execution_time = et - st
        print(f"Tempo de Execução - Desbastagem: {execution_time_ROD:.2f} segundos")
        print(f"Tempo de Execução - Trefilagem: {execution_time_Tref:.2f} segundos")
        print(f"Tempo de Execução - Torção: {execution_time_Torc:.2f} segundos")
        print(f"Tempo de Execução - Total: {execution_time:.2f} segundos\n")
        return True  # Indicate successful completion

    except Exception as e:
        print(f"Error during execution: {e}")
        return False


