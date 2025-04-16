from ortools.linear_solver import pywraplp
from itertools import product, groupby, chain
import copy
from datetime import datetime, timedelta, time
import time as tm
import pyodbc
import random
import math
from collections import Counter, defaultdict
from .utils import (TimeUnit, Items)

class RODPandS():
    def __init__(self, DataHandler):
        self.DataHandler = DataHandler
        self.Machines, self.RODItems = self.DataHandler.RODMachines, self.DataHandler.RODItems
        self.InitialSolution = self.Operations = self.MachinePreviousPlanCoT = None

    def generateSolution(self, Combination):
        '''Generates a randomized initial solution.'''
        initial_solution = {machine.MachineCode: [] for machine in self.Machines if machine.IsActive}  # Use machine names
        sorted_exec_plans = sorted(Combination, key=lambda x: x.ProductionOrder.DD)
        operations = {i + 1: ep for i, ep in enumerate(sorted_exec_plans)}

        possible_machines = []
        for op_number, data in operations.items():
            for routing in self.DataHandler.Routings:
                if routing.Item == data.ItemRelated.Name:
                    for machine in self.Machines:
                        if machine.IsActive and routing.Machine == machine.MachineCode and machine not in possible_machines:
                            possible_machines.append(machine)

        total_operations = len(operations)

        # Calculate total machine output capacity
        total_output_capacity = sum(machine.Output for machine in possible_machines)

        # Calculate number of operations per machine based on output capacity
        operations_per_machine = {
            machine.MachineCode: round((machine.Output / total_output_capacity) * total_operations)
            for machine in possible_machines
        }

        # Adjust operations to make sure the sum equals total_operations
        assigned_operations = sum(operations_per_machine.values())
        remainder = total_operations - assigned_operations

        # Distribute remainder operations if necessary
        if remainder > 0:
            for machine in possible_machines:
                operations_per_machine[machine.MachineCode] += 1
                remainder -= 1
                if remainder == 0:
                    break

        product_batches = {}
        for op_number, data in operations.items():
            product_name = data.ItemRelated.Name
            prod_order_id = data.ProductionOrder.id
            # Create a unique key for each product type and due date
            product_key = (product_name, prod_order_id)
            if product_key not in product_batches:
                product_batches[product_key] = []
            product_batches[product_key].append(op_number)

        for _, op_n in product_batches.items():
            for op_number, data in operations.items():
                if op_number in op_n:
                    possible_machines = [machine for routing in self.DataHandler.Routings if
                                         routing.Item == data.ItemRelated.Name
                                         for machine in self.Machines if machine.IsActive and routing.Machine == machine.MachineCode]
                    if self.DataHandler.Criteria[1]:
                        machine_cycle_weight = {}
                        for routing in self.DataHandler.Routings:
                            if routing.Item == data.ItemRelated.Name:
                                cycle_time = (routing.CycleTime / 1000) * data.ProductionOrder.Quantity
                                weight = routing.Weight
                                machine_cycle_weight[routing.Machine] = (cycle_time, weight)

                        # Sort possible machines by cycle time, using the highest weight as a tiebreaker
                        possible_machines.sort(key=lambda machine: (
                            machine_cycle_weight.get(machine.MachineCode, (float('inf'), float('-inf')))[0],
                            -machine_cycle_weight.get(machine.MachineCode, (float('inf'), float('-inf')))[1]
                        ))
                    # Choose the machine with highest weight
                    else:
                        machine_weight = {}
                        for routing in self.DataHandler.Routings:
                            if routing.Item == data.ItemRelated.Name:
                                machine_weight[routing.Machine] = routing.Weight
                        possible_machines.sort(
                            key=lambda machine: machine_weight.get(machine.MachineCode, float('inf')), reverse=True
                        )
                    # Sort possible machines by processing time
                    if possible_machines:
                        for _, (machine) in enumerate(possible_machines):
                            machine_name = machine.MachineCode
                            if machine.Output == 1 and len(initial_solution[machine_name]) >= operations_per_machine[
                                machine_name]:
                                continue  # Skip to the next machine
                            elif machine.Output > 1:
                                total_items = sum(len(subsolution) for subsolution in initial_solution[machine_name])
                                if total_items >= operations_per_machine[machine_name]:
                                    continue
                            # Assign the operation to the machine
                            if machine.Output > 1:
                                added = False
                                for subsolution in initial_solution[machine_name]:
                                    # Check if the sublist contains items from the same product and has space
                                    if (len(subsolution) < machine.Output and
                                            operations[subsolution[0]].ItemRelated.Name == data.ItemRelated.Name and
                                            operations[subsolution[0]].ProductionOrder.id == data.ProductionOrder.id):
                                        subsolution.append(op_number)
                                        added = True
                                        break

                                # If no suitable sublist found, create a new one for this product
                                if not added:
                                    initial_solution[machine_name].append([op_number])
                            else:
                                # For machines with output 1, simply add the operation
                                initial_solution[machine_name].append(op_number)
                            break

        MachinePreviousPlanCoT = {machine: self.getPreviousPlanCoT(machine) or None for machine in initial_solution}

        # print(
        #    "Initial Random Solution with Operations Ordered by Ascending Due Date and Placed in Machines with Least Processing Time: {}".format(
        #        initial_solution))

        self.InitialSolution, self.Operations, self.MachinePreviousPlanCoT = initial_solution, operations, MachinePreviousPlanCoT
        
    def getSetupTime(self, prev_type, cur_type):
        return next((float(instance.SetupTime) for instance in self.DataHandler.SetupTimesByMaterial
                     if instance.FromMaterial == prev_type and instance.ToMaterial == cur_type), 0.0)

    def getCycleTime(self, machine, item_name):
        return next(((routing.CycleTime / 1000) for routing in self.DataHandler.Routings
                     if routing.Item == item_name and routing.Machine == machine), None)

    def getMaterialType(self, item_name):
        return next((ROD_item.MaterialType for ROD_item in self.RODItems if ROD_item.Name == item_name),
                    None)

    def nextShiftStartTime(self, current_time, shift_start_times):
        for shift_start in shift_start_times:
            shift_start_dt = datetime.combine(current_time.date(), shift_start)
            if current_time < shift_start_dt:
                return shift_start_dt
        return datetime.combine(current_time.date() + timedelta(days=1), shift_start_times[0])

    def getPreviousPlanCoT(self, machine):
        """Get the Completion Time of the latest Execution Plan in the current machine"""
        shift_start_times = [time(0, 0), time(8, 0), time(16, 0)]

        with pyodbc.connect(self.DataHandler.ConnectionString) as conn, conn.cursor() as cursor:
            # Get latest execution plan for the machine
            cursor.execute(
                """SELECT TOP 1 ep.Item, ep.CompletionTime 
                   FROM ExecutionPlans ep 
                   JOIN Items i ON ep.Item COLLATE SQL_Latin1_General_CP1_CI_AS = i.Item 
                   WHERE i.Process = 'ROD' AND ep.Machine = ? 
                   ORDER BY CompletionTime DESC""", 
                (machine,)
            )
            result = cursor.fetchone()
            latest_ep_item, previous_plan_CoT = result if result else (None, None)
            
        # Determine start time
        start_time = max(previous_plan_CoT, self.DataHandler.CurrentTime) if previous_plan_CoT else self.DataHandler.CurrentTime
            
        return [latest_ep_item, self.nextShiftStartTime(start_time, shift_start_times)]

    def getSTandCoT(self, data, CT, machine_ST, previous_item_CoT, setup_time):
        data.ST = (previous_item_CoT + timedelta(hours=setup_time)) if previous_item_CoT else machine_ST
        data.ST += timedelta(minutes=(CT * 0.12))
        data.CoT = data.ST + timedelta(minutes=CT)

    def Planning(self):
        # Gather all unique MDW-related items
        tref_list = {exec_plan.ItemRelated for exec_plan in self.DataHandler.ExecutionPlans if
                     exec_plan.ItemRelated.Process == "MDW"}

        # Create ROD execution plans for each MDW item
        ROD_exec_plans = {}
        for tref_item in tref_list:
            exec_plan_list = []
            temp_list = []
            for exec_plan in self.DataHandler.ExecutionPlans:
                if exec_plan.ItemRelated.Process == "ROD" and exec_plan.ItemRoot.Name == tref_item.Name:
                    if temp_list and exec_plan.BoMId != temp_list[-1].BoMId:
                        exec_plan_list.append(temp_list)
                        temp_list = []
                    temp_list.append(exec_plan)
            if temp_list:
                exec_plan_list.append(temp_list)
            if exec_plan_list:
                ROD_exec_plans[tref_item.Name] = exec_plan_list

        # Generate and evaluate all combinations of ROD execution plans
        ROD_combinations = [list(chain.from_iterable(combination)) for combination in product(*ROD_exec_plans.values())]
        print("Total Número de Combinações - Desbastagem:", len(ROD_combinations))

        best_solution, best_objValue = None, 0
        for data in ROD_combinations:
            self.generateSolution(data)
            objValue = self.objFun(self.InitialSolution)
            if objValue >= best_objValue:
                best_solution, best_objValue = self.InitialSolution, objValue

        self.DataHandler.RODSolution = best_solution

        for machine, operations in self.DataHandler.RODSolution.items():
            if not operations:
                continue

            output = next(mach.Output for mach in self.Machines if mach.IsActive and mach.MachineCode == machine)

            # Only proceed if the machine has multiple batches (i.e., list of lists)
            if isinstance(operations[0], list):
                # Collect sublists by product name
                grouped_by_name = {}
                for i, op_group in enumerate(operations):
                    if len(op_group) < output:  # Only consider groups smaller than output
                        for op in op_group:
                            data = self.Operations[op]
                            item_name = data.ItemRelated.Name
                            if item_name not in grouped_by_name:
                                grouped_by_name[item_name] = []
                            grouped_by_name[item_name].append((i, op))  # Store index and operation

                # Now, merge groups of the same product type
                for item_name, ops in list(grouped_by_name.items()):  # Use list() to allow modifying dict
                    # Sort by index so that we fill earlier groups first
                    ops.sort()

                    # Track the group we're currently filling
                    current_group_index = ops[0][0]
                    current_group = operations[current_group_index]

                    # Continue merging until all unfilled groups are handled
                    for idx, op in ops[1:]:  # Start from the second op group onward
                        if len(current_group) < output:  # Keep filling the current group
                            # Add the operation to the current group
                            current_group.append(op)
                            # Remove the operation from the donor group
                            operations[idx].remove(op)
                        else:
                            current_group_index = idx
                            current_group = operations[current_group_index]

                    # After merging, remove empty groups and ensure no group exceeds output capacity
                    operations = [group for group in operations if len(group) > 0]

                # Update the machine's operations in BestSolution after merging
                self.DataHandler.RODSolution[machine] = operations

    def Scheduling(self):
        """Add Starting Time (ST) and Completion Time (CoT) to each Execution Plan using the final solution."""
        for machine, operations in self.DataHandler.RODSolution.items():
            if not operations:
                continue
            previous_plan_CoT = self.MachinePreviousPlanCoT[machine][1]
            previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
            previous_item_CoT = current_type = None
            for i, op in enumerate(operations):
                Max_CoT = self.DataHandler.CurrentTime.replace(hour=0, minute=0, second=0, microsecond=0)
                if isinstance(op, list):
                    for j, op_n in enumerate(op):
                        data = self.Operations[op_n]
                        data.Machine = machine
                        current_type = self.getMaterialType(data.ItemRelated.Name)
                        CT = self.getCycleTime(machine, data.ItemRelated.Name) * data.Quantity
                        setup_time = self.getSetupTime(previous_type, current_type) if previous_type != current_type else 0.0
                        self.getSTandCoT(data, CT, previous_plan_CoT, previous_item_CoT, setup_time)
                        data.Position = j + 1
                        op[j] = [op_n, data]
                        Max_CoT = max(Max_CoT, data.CoT)
                    previous_type = current_type
                else:
                    data = self.Operations[op]
                    data.Machine = machine
                    current_type = self.getMaterialType(data.ItemRelated.Name)
                    CT = self.getCycleTime(machine, data.ItemRelated.Name) * data.Quantity
                    setup_time = self.getSetupTime(previous_type, current_type) if previous_type != current_type else 0.0
                    self.getSTandCoT(data, CT, previous_plan_CoT, previous_item_CoT, setup_time)
                    operations[i] = [op, data]
                    Max_CoT = data.CoT
                    data.Position = 1
                    previous_type = current_type
                previous_item_CoT = Max_CoT

        self.removeExecPlans()

    def removeExecPlans(self):
        # Remove execution plans that are not part of the best ROD solution
        plans_to_exclude = []
        for exec_plan in self.DataHandler.ExecutionPlans:
            if exec_plan.ItemRelated.Process == "ROD":
                exec_plan_found = any(
                    exec_plan.id == op[1].id for _, operations in self.DataHandler.RODSolution.items() for op_pair
                    in operations for op in (op_pair if isinstance(op_pair[0], list) else [op_pair]))
                if not exec_plan_found:
                    plans_to_exclude.append(exec_plan.id)

        for ep_id in plans_to_exclude:
            self.DataHandler.removeEPbyID(ep_id)

    def objFun(self, solution):
        '''Calculate the objective function value for the given solution. Objective - Minimize tardiness'''
        objfun_value = 0
        for machine, operations in solution.items():
            if not operations:
                continue
            previous_plan_CoT = self.MachinePreviousPlanCoT[machine][1]
            previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
            previous_item_CoT = None
            for op in operations:
                Max_CoT = self.DataHandler.CurrentTime.replace(hour=0, minute=0, second=0, microsecond=0)
                ops = op if isinstance(op, list) else [op]
                for op_n in ops:
                    if op_n in self.Operations:
                        data = self.Operations[op_n]
                        current_type = self.getMaterialType(data.ItemRelated.Name)
                        CT = self.getCycleTime(machine, data.ItemRelated.Name) * data.Quantity
                        setup_time = self.getSetupTime(previous_type, current_type) if previous_type != current_type else 0.0
                        self.getSTandCoT(data, CT, previous_plan_CoT, previous_item_CoT, setup_time)
                        DD = data.ProductionOrder.DD
                        Tardiness = max(data.CoT - DD, timedelta(0))
                        Max_CoT = max(Max_CoT, data.CoT)
                        # objfun_value += (Tardiness.total_seconds() / 60) / data.ProductionOrder.Weight
                        objfun_value += (Tardiness.total_seconds() / 60)
                        previous_type = current_type
                # objfun_value += ((Max_CoT - machine_ST).total_seconds() / 60)
                previous_item_CoT = Max_CoT

        return objfun_value


class TrefPandS():
    def __init__(self, DataHandler):
        self.DataHandler = DataHandler
        self.Machines, self.TorcItems, self.TrefItems = self.DataHandler.TrefMachines, self.DataHandler.TorcItems, self.DataHandler.TrefItems

    def combineItems(self, combination):
        combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids, type_list = [], [], [], [], [], []

        type_list = list({exec_plan.ItemRelated.MaterialType for exec_plan in combination})

        for exec_plan in combination:
            if exec_plan.ItemRelated.MaterialType == type_list[0]:
                weights_names.append(exec_plan.ItemRelated.Name)
                combined_weights.append(exec_plan.ItemRelated.Input)
                combined_values.append("1")
                weights_PO.append(exec_plan.ProductionOrder)
                exec_plan_ids.append(exec_plan.id)

        return combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids

    def chooseBestSolution(self, current_solution_weight, current_solution_value, current_solution_size,
                           best_solution_weight, best_solution_value, best_solution_size):
        if current_solution_value > best_solution_value:
            return True
        if current_solution_value == best_solution_value:
            if current_solution_size < best_solution_size or current_solution_weight > best_solution_weight:
                return True
        return False

    def Planning(self):
        """Get the allocation of the tref items throughout the machines, get the CT (Completion Time) of each Execution Plan,
        order the calculated solutions by average DD (Due Date), and finally create the Time Units and assign the according ST, ET and CT"""
        best_solutions = self.execPlanCombinations()
        
        plans_to_exclude = []
        for exec_plan in self.DataHandler.ExecutionPlans:
            exec_plan_found = False
            for solutions in best_solutions:
                for solution in solutions:
                    for machine in self.Machines:
                        if machine.IsActive and (exec_plan.id in solution["allocated_exec_plans"][machine.MachineCode] or
                                exec_plan.ItemRelated.Process == "BUN"):
                            exec_plan_found = True
                            if exec_plan.id in plans_to_exclude:
                                plans_to_exclude.remove(exec_plan.id)
            if not exec_plan_found:
                plans_to_exclude.append(exec_plan.id)

        for ep_id in plans_to_exclude:
            self.DataHandler.removeEPbyID(ep_id)

        for solutions in best_solutions:
            for _, solution in enumerate(solutions):
                for machine in self.Machines:
                    TUCount = 0
                    if machine.IsActive and solution["individual_weights_POs"][machine.MachineCode]:
                        timeUnit = TimeUnit(machine.MachineCode)
                        self.DataHandler.TimeUnits.append(timeUnit)
                        for exec_plan in self.DataHandler.ExecutionPlans:
                            for exec_plan_id in solution["allocated_exec_plans"][machine.MachineCode]:
                                if exec_plan.id == exec_plan_id:
                                    timeUnit.ExecutionPlans.append(exec_plan)
                                    exec_plan.Machine = machine.MachineCode
                                    TUCount += 1
                                    exec_plan.Position = TUCount

    def Scheduling(self, PT_Settings):
        # Helper function to sort time units based on the configured criteria
        def sort_time_units(TU_list, machine):
            sort_criteria = []

            # Append sort criteria based on the enabled criteria
            if self.DataHandler.Criteria[2]:
                # Check if the we should organize the Time Units in ascending or descending order according to the average diameter
                with pyodbc.connect(self.DataHandler.ConnectionString) as conn:
                    with conn.cursor() as cursor:
                        # Query to get the ExecutionPlan with the biggest CompletionTime for the machine
                        cursor.execute("""
                                SELECT TOP 1 ep.Item
                                FROM ExecutionPlans ep
                                WHERE Machine = ?
                                ORDER BY CompletionTime DESC
                            """, (machine,))

                        result = cursor.fetchone()  # Fetch the first result
                        execution_plan = result[0] if result else None

                max_dia = min_dia = None
                if execution_plan:
                    diameters = [Items.get_Item(TU_exec_plan.ItemRelated.Name, self.DataHandler.Database).Diameter
                                 for TU in TU_list for TU_exec_plan in TU.ExecutionPlans]

                    max_dia, min_dia = max(diameters), min(diameters)
                    last_item_dia = Items.get_Item(execution_plan, self.DataHandler.Database).Diameter

                    if min_dia < last_item_dia < max_dia:
                        sort_criteria.append(lambda x: -x.get_average_diameter(self.DataHandler.Database)
                        if (max_dia - last_item_dia) < (last_item_dia - min_dia)
                        else x.get_average_diameter(self.DataHandler.Database))
                    else:
                        sort_criteria.append(lambda
                                                 x: -x.get_average_diameter(self.DataHandler.Database) if last_item_dia > max_dia or last_item_dia == max_dia else x.get_average_diameter(self.DataHandler.Database))
                else:
                    sort_criteria.append(lambda x: -x.get_average_diameter(self.DataHandler.Database))

            if self.DataHandler.Criteria[4]:
                sort_criteria.append(lambda x: x.get_primary_material_type())
            # Add average due date as a primary sorting criterion
            sort_criteria.append(lambda x: x.calculate_average_due_date())

            # Add weight as a tiebreaker when due dates are the same
            sort_criteria.append(lambda x: -x.get_average_weight())

            # Combine all sort criteria into a single sorting key
            key_func = lambda x: tuple(criteria(x) for criteria in sort_criteria)
            return sorted(TU_list, key=key_func) if sort_criteria else TU_list

        def update_exec_plan(exec_plan_dict, TU):
            for TU_exec_plan in TU.ExecutionPlans:
                if TU_exec_plan.id in exec_plan_dict:
                    exec_plan = exec_plan_dict[TU_exec_plan.id]
                    CT = next(
                        (routing.CycleTime for routing in self.DataHandler.Routings
                         if routing.Item == exec_plan.ItemRelated.Name and routing.Machine == TU.Machine),
                        None)
                    CT = (CT / 1000) * exec_plan.Quantity
                    exec_plan.ST = TU.ST
                    exec_plan.CoT = exec_plan.ST + timedelta(minutes=CT)

        # Initialize structures
        if PT_Settings:
            ST_TU, item_count_dict = {}, {}
            # Extract initial CoT for the first time unit in each machine
            for machine in self.Machines:
                if machine.IsActive:
                    TU_list = [tu for tu in self.DataHandler.TimeUnits if machine.MachineCode == tu.Machine]
                    if not TU_list:
                        continue

                sorted_tu_list = sort_time_units(TU_list, machine.MachineCode)

                ROD_items = {}
                for TU_exec_plan in sorted_tu_list[0].ExecutionPlans:
                    qty = TU_exec_plan.ItemRelated.Input
                    for bom in self.DataHandler.BoMs:
                        if bom.ItemRoot == TU_exec_plan.ItemRelated.Name:
                            for BoM_Item in bom.BoMItems:
                                ROD_items[BoM_Item.ItemRelated] = ROD_items.get(BoM_Item.ItemRelated, 0) + qty

                Max_CoT, item_count, current_count = self.calculateTrefST(ROD_items, [], {}, self.DataHandler)
                if item_count:
                    ST_TU[machine.MachineCode] = [Max_CoT, item_count, current_count]
                item_count_dict[machine.MachineCode] = item_count

            # Determine the order of machines based on their CoT
            order = []
            while ST_TU:
                # Find the machine with the earliest CoT
                earliest_machine = min(ST_TU, key=lambda x: ST_TU[x][0])
                order.append((earliest_machine, ST_TU[earliest_machine][0]))
                previous_count = copy.deepcopy(ST_TU[earliest_machine][2])
                del ST_TU[earliest_machine]

                # Update CoT_TU for the remaining machines
                for machine in list(ST_TU.keys()):
                    TU_list = [tu for tu in self.DataHandler.TimeUnits if machine == tu.Machine]
                    if not TU_list:
                        continue

                    sorted_tu_list = sort_time_units(TU_list, machine)
                    ROD_items = {}
                    for TU_exec_plan in sorted_tu_list[0].ExecutionPlans:
                        qty = TU_exec_plan.ItemRelated.Input
                        for bom in self.DataHandler.BoMs:
                            if bom.ItemRoot == TU_exec_plan.ItemRelated.Name:
                                for BoM_Item in bom.BoMItems:
                                    ROD_items[BoM_Item.ItemRelated] = ROD_items.get(BoM_Item.ItemRelated, 0) + qty

                    Max_CoT, updated_item_count, current_count = self.calculateTrefST(
                        ROD_items,
                        item_count_dict.get(machine, []),
                        copy.deepcopy(previous_count),
                        self.DataHandler
                    )
                    ST_TU[machine] = [Max_CoT, updated_item_count, current_count]
                    item_count_dict[machine] = updated_item_count

            for machine, start_time in order:
                TU_list = [tu for tu in self.DataHandler.TimeUnits if machine == tu.Machine]
                previous_TU = None
                sorted_tu_list = sort_time_units(TU_list, machine)
                for TU in sorted_tu_list:
                    TU.calculate_time(start_time, previous_TU, self.DataHandler, self.DataHandler.CurrentTime)
                    previous_TU = TU

            exec_plan_dict = {exec_plan.id: exec_plan for exec_plan in self.DataHandler.ExecutionPlans}
            for TU in self.DataHandler.TimeUnits:
                update_exec_plan(exec_plan_dict, TU)
        else:
            for machine in self.Machines:
                if machine.IsActive:
                    TU_list = [tu for tu in self.DataHandler.TimeUnits if machine.MachineCode == tu.Machine]
                    if not TU_list:
                        continue

                previous_TU = None
                sorted_tu_list = sort_time_units(TU_list, machine.MachineCode)
                for TU in sorted_tu_list:
                    TU.calculate_time(None, previous_TU, self.DataHandler, self.DataHandler.CurrentTime)
                    previous_TU = TU

            exec_plan_dict = {exec_plan.id: exec_plan for exec_plan in self.DataHandler.ExecutionPlans}
            for TU in self.DataHandler.TimeUnits:
                update_exec_plan(exec_plan_dict, TU)

    def calculateTrefST(self, ROD_items, item_count, current_count, data_handler):
        Max_CoT = self.DataHandler.CurrentTime.replace(hour=0, minute=0, second=0, microsecond=0)
        item_count_aux = {}
        for _, (item, qty) in enumerate(ROD_items.items()):
            machines_with_item = {}
            # Identify machines that contain the item
            for x, (mach_name, operations) in enumerate(data_handler.RODSolution.items()):
                for op_pair in operations:
                    if isinstance(op_pair[0], list):
                        for op in op_pair:
                            if op[1].ItemRelated.Name == item:
                                if mach_name not in machines_with_item:
                                    mach = next((m for m in self.DataHandler.RODMachines if m.IsActive and m.MachineCode == mach_name), None)
                                    if mach:
                                        machines_with_item[mach] = x
                                        break
                    else:
                        if op_pair[1].ItemRelated.Name == item:
                            if mach_name not in machines_with_item:
                                mach = next((m for m in self.DataHandler.RODMachines if m.IsActive and m.MachineCode == mach_name), None)
                                if mach:
                                    machines_with_item[mach] = x
                                    break

            # Distribute quantities among the identified machines
            if not item_count:
                total_input_capacity = sum(mach.Input for mach in machines_with_item.keys())
                temp_results = [int(mach.Input / total_input_capacity * qty) for mach in machines_with_item.keys()]
                remaining_qty = qty - sum(temp_results)

                for idx in range(remaining_qty):
                    temp_results[idx % len(temp_results)] += 1

                results = [0] * len([machine for machine in self.DataHandler.RODMachines if machine.IsActive])
                for idx, mach_name in enumerate(machines_with_item.values()):
                    results[mach_name] = temp_results[idx]

                item_count_aux[item] = results
                current_count[item] = [0] * len([machine for machine in self.DataHandler.RODMachines if machine.IsActive])
            else:
                for ROD_item in self.DataHandler.Items:
                    if item == ROD_item.Name:
                        current_counts = item_count.get(item, [0] * len([machine for machine in self.DataHandler.RODMachines if machine.IsActive]))
                        item_count_aux[item] = [y for x, y in enumerate(current_counts)]

            for j, (mach, operations) in enumerate(data_handler.RODSolution.items()):
                iter = current_count.get(item, [0] * len([machine for machine in self.DataHandler.RODMachines if machine.IsActive]))[j]
                count = 0
                while count < item_count_aux[item][j]:
                    if iter >= len(operations):
                        break
                    if isinstance(operations[iter][0], list):
                        for op_pair in operations[iter]:
                            if op_pair[1].ItemRelated.Name == item:
                                count += 1
                                Max_CoT = max(Max_CoT, op_pair[1].CoT)
                    else:
                        if operations[iter][1].ItemRelated.Name == item:
                            count += 1
                            Max_CoT = max(Max_CoT, operations[iter][1].CoT)
                    iter += 1
                if item in current_count:
                    current_count[item][j] = iter
        return Max_CoT, item_count_aux, current_count

    def execPlanCombinations(self):
        # Group the Execution Plans by Production Order and generate combinations in batches of 25.
        best_solutions = []
        processed_combinations = 0
        max_no_improvement = 1000  # Stop after 1000 iterations without improvement within a batch

        # Sort production orders by due date
        sorted_prod_orders = sorted(self.DataHandler.ProductionOrders, key=lambda po: po.DD)

        # Initialize prod_exec_plans as a dictionary
        prod_exec_plans = {}

        for prod_order in sorted_prod_orders:
            # Filter execution plans by production order ID and exclude BUN process
            filtered_plans = [ep for ep in self.DataHandler.ExecutionPlans if
                              ep.ProductionOrder.id == prod_order.id and ep.ItemRelated.Process != "BUN"]

            # Sort filtered plans by ItemRoot.Name for grouping
            sorted_by_root = sorted(filtered_plans, key=lambda ep: ep.ItemRoot.Name)

            # Initialize list for each production order's BoM combinations
            root_ep_list = []

            for _, group_by_root in groupby(sorted_by_root, key=lambda ep: ep.ItemRoot.Name):
                # Sort by BoMId for secondary grouping
                sorted_by_bomid = sorted(group_by_root, key=lambda ep: ep.BoMId)

                # Collect grouped lists by BoMId as individual combinations
                bomid_group = [list(group_by_bomid) for _, group_by_bomid in
                               groupby(sorted_by_bomid, key=lambda ep: ep.BoMId)]

                root_ep_list.append(bomid_group)

            # Store root_ep_list in dictionary with prod_order.id as the key, flattening one level to fit the combination structure
            prod_exec_plans[prod_order.id] = list(product(*root_ep_list))

        batch_size = 25
        for i in range(0, len(sorted_prod_orders), batch_size):
            best_solution = None
            best_solution_weight, best_solution_value, best_solution_size = 0, 0, 0

            batch_prod_orders = sorted_prod_orders[i:i + batch_size]

            # Filter the exec plans for this batch
            batch_exec_plans = {
                prod_order.id: prod_exec_plans[prod_order.id]
                for prod_order in batch_prod_orders
                if prod_order.id in prod_exec_plans
            }

            if not batch_exec_plans:
                continue

            no_improvement_iterations = 0  # Reset for each batch

            # Generate combinations for the current batch
            for combination in product(*batch_exec_plans.values()):
                st = tm.time()
                flattened_combination = list(chain.from_iterable(chain.from_iterable(combination)))
                # Process the combination and get the according solution, weight and value
                current_solution, current_solution_weight, current_solution_value = self.processCombinations(
                    flattened_combination)
                et = tm.time()
                print(f"Combination processing time: {et - st} seconds")

                # Check if the current solution is better than the best one
                flag = self.chooseBestSolution(
                    current_solution_weight, current_solution_value, len(current_solution),
                    best_solution_weight, best_solution_value, best_solution_size
                )
                if flag:
                    # Update the best solution if the current one is better
                    best_solution = current_solution
                    best_solution_weight, best_solution_value, best_solution_size = (
                        current_solution_weight, current_solution_value, len(current_solution)
                    )
                    no_improvement_iterations = 0  # Reset if an improvement is found
                else:
                    no_improvement_iterations += 1
                processed_combinations += 1
                print("No improvement: ", no_improvement_iterations)

                # Stop processing combinations within this batch if no improvement is found after 1000 iterations
                if no_improvement_iterations >= max_no_improvement:
                    # print(f"No improvement for {max_no_improvement} iterations, moving to next batch.")
                    break

            best_solutions.append(best_solution)

        # global total_combinations
        # print(f"Total Número de Combinações - Trefilagem: {total_combinations}")
        print(f"Total Número de Combinações Processadas - Trefilagem: {processed_combinations}")
        return best_solutions

    """def processCombinations(self, combination):
        def get_CTs_and_Weights_cache(tref_items, routings, bins, bins_index):
            # Precompute the cycle times and weights
            cycle_times = {item: [0] * len(bins_index) for item in tref_items}
            weights = {item: [0] * len(bins_index) for item in tref_items}

            bin_map = {bin_code: idx for idx, bin_code in enumerate(bins)}  # Precompute bin index lookups

            for routing in routings:
                item = routing.Item
                if item in tref_items and routing.Machine in bin_map:
                    bin_idx = bin_map[routing.Machine]
                    cycle_times[item][bin_idx] = routing.CycleTime
                    weights[item][bin_idx] = routing.Weight
            return cycle_times, weights

        current_solution = []
        current_solution_weight, current_solution_value = 0, 0
        combination_copy = combination[:]  # Copy for safe iteration
        item_assignment = {}

        # Group exec_plans by priority (ProductionOrder.Weight)
        priority_groups = {}
        for exec_plan in combination_copy:
            priority = exec_plan.ProductionOrder.Weight
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(exec_plan)

        # Process priorities from highest to lowest
        sorted_priorities = sorted(priority_groups.keys(), reverse=True)

        # Prepare the data structure for bins, weights, etc.
        data = {
            "bins": [machine.MachineCode for machine in self.Machines],
            "bin_capacities": [machine.Input for machine in self.Machines],
            "output_capacities": [machine.Output for machine in self.Machines],
            "weights": [],
            "values": [],
            "weights_name": [],
            "weights_PO": [],
            "exec_plan_ids": []
        }

        machine_completion_times = {machine.MachineCode: 0 for machine in self.Machines}
        excluded_machines = set()

        for priority in sorted_priorities:
            priority_exec_plans = priority_groups[priority]

            # Convert exec_plans to data structure
            combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids = self.combineItems(priority_exec_plans)

            data.update({
                "weights": combined_weights,
                "values": combined_values,
                "weights_name": weights_names,
                "weights_PO": weights_PO,
                "exec_plan_ids": exec_plan_ids,
                "num_items": len(combined_weights),
                "all_items": range(len(combined_weights)),
                "num_bins": len(data["bin_capacities"]),
                "all_bins": range(len(data["bin_capacities"]))
            })

            all_items = [exec_plan.ItemRelated.Name for exec_plan in priority_exec_plans]
            cycle_times, item_weights = get_CTs_and_Weights_cache(
                all_items, self.DataHandler.Routings, data["bins"], data["all_bins"]
            )

            while priority_exec_plans:
                all_current_items = [exec_plan.ItemRelated.Name for exec_plan in priority_exec_plans]
                excluded_machines_copy = excluded_machines.copy()

                # Check if all items only have routings on excluded machines
                all_routings_excluded = all(
                    not any(
                        ct > 0 and data["bins"][bin_idx] not in excluded_machines
                        for bin_idx, ct in enumerate(cycle_times[item])
                    )
                    for item in all_current_items
                )

                if all_routings_excluded:
                    excluded_machines.clear()

                # Solve with KPMILP using the cached cycle_times and item_weights
                solution = self.KPMILP(data, cycle_times, item_weights, item_assignment, excluded_machines)
                if solution:
                    current_solution.append(solution)
                    current_solution_weight += solution["total_packed_weight"]
                    current_solution_value += solution["total_objective_value"]

                    for machine, items in solution["individual_weights_names"].items():
                        for item in items:
                            if item not in item_assignment:
                                item_assignment[item] = machine

                    # Remove allocated items and update machine completion times
                    to_remove = []
                    for exec_plan in priority_exec_plans:
                        for machine in self.Machines:
                            allocated_exec_plans = solution["allocated_exec_plans"][machine.MachineCode]
                            if exec_plan.id in allocated_exec_plans:
                                to_remove.append(exec_plan)
                                machine_completion_times[machine.MachineCode] += sum(
                                    cycle_times[exec_plan.ItemRelated.Name][
                                        data["bins"].index(machine.MachineCode)
                                    ] * exec_plan.Quantity
                                    for exec_plan in priority_exec_plans if exec_plan.id in allocated_exec_plans
                                )

                    # Temporarily exclude machines exceeding the threshold
                    active_completion_times = [comp_time for comp_time in machine_completion_times.values() if comp_time > 0]
                    avg_completion_time = sum(active_completion_times) / len(active_completion_times) if active_completion_times else 0

                    for machine_code, comp_time in machine_completion_times.items():
                        if comp_time > avg_completion_time:
                            excluded_machines.add(machine_code)
                        elif machine_code in excluded_machines and comp_time <= avg_completion_time:
                            excluded_machines.remove(machine_code)

                    # Remove allocated exec_plans
                    for exec_plan in to_remove:
                        priority_exec_plans.remove(exec_plan)
                        
                    combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids = self.combineItems(priority_exec_plans)
    
                    data.update({
                        "weights": combined_weights,
                        "values": combined_values,
                        "weights_name": weights_names,
                        "weights_PO": weights_PO,
                        "exec_plan_ids": exec_plan_ids,
                        "num_items": len(combined_weights),
                        "all_items": range(len(combined_weights)),
                        "num_bins": len(data["bin_capacities"]),
                        "all_bins": range(len(data["bin_capacities"]))
                    })

                # Restore original excluded machines list after each KPMILP call
                if excluded_machines_copy:
                    excluded_machines = excluded_machines_copy

        return current_solution, current_solution_weight, current_solution_value"""
    
    def processCombinations(self, combination):
        def get_CTs_and_Weights_cache(tref_items, routings, bins, bins_index):
            # Precompute the cycle times and weights
            cycle_times = {item: [0] * len(bins_index) for item in tref_items}
            weights = {item: [0] * len(bins_index) for item in tref_items}

            bin_map = {bin_code: idx for idx, bin_code in enumerate(bins)}  # Precompute bin index lookups

            for routing in routings:
                item = routing.Item
                if item in tref_items and routing.Machine in bin_map:
                    bin_idx = bin_map[routing.Machine]
                    cycle_times[item][bin_idx] = routing.CycleTime
                    weights[item][bin_idx] = routing.Weight
            return cycle_times, weights

        current_solution = []
        current_solution_weight, current_solution_value = 0, 0
        combination_copy = copy.deepcopy(combination)
        # Make sure that all same items are assigned to the same machine. Once the 1st one of is assigned to a machine
        # all the next ones have to be assigned to the same one.
        item_assignment = {}

        # Prepare the data structure for bins, weights, etc.
        data = {
            "weights": [], "values": [], "bins": [], "bin_capacities": [],
            "weights_name": [], "weights_PO": [], "exec_plan_ids": [], "output_capacities": []
        }

        for machine in self.Machines:
            if machine.IsActive:
                data["bins"].append(machine.MachineCode)
                data["bin_capacities"].append(machine.Input)
                data["output_capacities"].append(machine.Output)

        combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids = self.combineItems(
            combination_copy)

        data.update({
            "weights": combined_weights,
            "values": combined_values,
            "weights_name": weights_names,
            "weights_PO": weights_PO,
            "exec_plan_ids": exec_plan_ids
        })

        num_items = len(data["weights"])
        num_bins = len(data["bin_capacities"])

        data.update({
            "num_items": num_items,
            "all_items": range(num_items),
            "num_bins": num_bins,
            "all_bins": range(num_bins)
        })

        all_items = [exec_plan.ItemRelated.Name for exec_plan in combination]
        # Precompute and cache cycle_times and item_weights for reuse
        cycle_times, item_weights = get_CTs_and_Weights_cache(
            all_items, self.DataHandler.Routings, data["bins"], data["all_bins"]
        )

        machine_completion_times = {machine.MachineCode: 0 for machine in self.Machines if machine.IsActive}
        excluded_machines = set()

        while combination_copy:
            all_current_items = [exec_plan.ItemRelated.Name for exec_plan in combination_copy]
            excluded_machines_copy = None

            # Backup current exclusions and check if all items are restricted to excluded machines
            all_routings_excluded = True

            # Check if all items only have routings on excluded machines
            for item in all_current_items:
                non_excluded_machine = any(
                    ct > 0 and data["bins"][bin_idx] not in excluded_machines
                    for bin_idx, ct in enumerate(cycle_times[item])
                )
                if non_excluded_machine:
                    all_routings_excluded = False
                    break

            # If all routings are on excluded machines, clear exclusions for this iteration
            if all_routings_excluded:
                excluded_machines_copy = excluded_machines.copy()
                excluded_machines.clear()

            # Solve with KPMILP using the cached cycle_times and item_weights
            solution = self.KPMILP(data, cycle_times, item_weights, item_assignment, excluded_machines)
            current_solution.append(solution)
            if solution:
                current_solution_weight += solution["total_packed_weight"]
                current_solution_value += solution["total_objective_value"]

                for machine, items in solution["individual_weights_names"].items():
                    for item in items:
                        if item not in item_assignment:
                            item_assignment[item] = machine

                # Collect the IDs of items to remove from combination_copy
                to_remove = []
                for exec_plan in combination_copy:
                    for machine in self.Machines:
                        if machine.IsActive:
                            allocated_exec_plans = solution["allocated_exec_plans"][machine.MachineCode]
                            if exec_plan.id in allocated_exec_plans:
                                to_remove.append(exec_plan)
                                # Update machine's completion time
                                machine_completion_times[machine.MachineCode] += sum(
                                    cycle_times[exec_plan.ItemRelated.Name][
                                        data["bins"].index(machine.MachineCode)] * exec_plan.Quantity
                                    for exec_plan in combination_copy if exec_plan.id in allocated_exec_plans)

                # Temporarily exclude machines exceeding the threshold
                active_completion_times = [comp_time for comp_time in machine_completion_times.values() if
                                           comp_time > 0]
                avg_completion_time = sum(active_completion_times) / len(active_completion_times) \
                    if active_completion_times else 0
                for machine_code, comp_time in machine_completion_times.items():
                    if comp_time > avg_completion_time:
                        excluded_machines.add(machine_code)
                    elif machine_code in excluded_machines and comp_time <= avg_completion_time:
                        excluded_machines.remove(machine_code)

                # Remove the allocated items from combination_copy and also from cycle_times and item_weights
                for exec_plan in to_remove:
                    combination_copy.remove(exec_plan)

                # Update the data for remaining items
                combined_weights, combined_values, weights_names, weights_PO, exec_plan_ids = self.combineItems(
                    combination_copy)
                data.update({
                    "weights": combined_weights,
                    "values": combined_values,
                    "weights_name": weights_names,
                    "weights_PO": weights_PO,
                    "exec_plan_ids": exec_plan_ids
                })
                num_items = len(data["weights"])
                num_bins = len(data["bin_capacities"])
                data.update({
                    "num_items": num_items,
                    "all_items": range(num_items),
                    "num_bins": num_bins,
                    "all_bins": range(num_bins)
                })

            # Restore original excluded machines list after each KPMILP call
            if excluded_machines_copy:
                excluded_machines = excluded_machines_copy

        return current_solution, current_solution_weight, current_solution_value

    def KPMILP(self, data, cycle_times, item_weights, item_assignment, excluded_machines):
        # Solver setup
        solver = pywraplp.Solver.CreateSolver("SCIP")

        # Only store variables that are actually used
        x = {}

        # Objective and machine choice cache
        objective = solver.Objective()
        chosen_machines = defaultdict(list)
        machine_diameter_counts = defaultdict(Counter)
        machine_common_diameter = {}

        # Precompute TrefItems lookup
        tref_items_dict = {t.Name: t for t in self.TrefItems}

        # Optimize loop over items and bins
        for i in data["all_items"]:
            tref_item = data["weights_name"][i]
            ct_values = cycle_times[tref_item]  # Direct lookup from cache
            # weight_values = item_weights[tref_item]  # Direct lookup from cache
            item_diameter = int(tref_items_dict[tref_item].Diameter * 1000)  # Precomputed

            for mach, ct in enumerate(ct_values):
                if ct > 0 and data["bins"][
                    mach] not in excluded_machines:  # Only process if cycle time is greater than zero
                    # weight = weight_values[mach]
                    if tref_item in item_assignment:
                        if item_assignment[tref_item] != data["bins"][mach]:
                            continue

                    # Update the diameter count for the current machine
                    machine_diameter_counts[mach][item_diameter] += 1

                    # Check if this diameter is now the most common for this machine
                    current_most_common = machine_common_diameter.get(mach, None)
                    if not current_most_common or machine_diameter_counts[mach][item_diameter] > \
                            machine_diameter_counts[mach][current_most_common]:
                        machine_common_diameter[mach] = item_diameter  # Update most common diameter
                    chosen_machines[mach].append(i)

        if not chosen_machines:
            for i in data["all_items"]:
                tref_item = data["weights_name"][i]
                ct_values = cycle_times[tref_item]  # Direct lookup from cache
                item_diameter = int(tref_items_dict[tref_item].Diameter * 1000)  # Precomputed

                for mach, ct in enumerate(ct_values):
                    if ct > 0 and data["bins"][
                        mach] not in excluded_machines:  # Only process if cycle time is greater than zero
                        # Skip the item_assignment check and assign freely to available machines
                        machine_diameter_counts[mach][item_diameter] += 1

                        # Check if this diameter is now the most common for this machine
                        current_most_common = machine_common_diameter.get(mach, None)
                        if not current_most_common or machine_diameter_counts[mach][item_diameter] > \
                                machine_diameter_counts[mach][current_most_common]:
                            machine_common_diameter[mach] = item_diameter  # Update most common diameter
                        chosen_machines[mach].append(i)

        # Create variables based on the diameter consistency constraint
        for mach, items in chosen_machines.items():
            most_common_diameter = machine_common_diameter[mach]
            for item in items:
                # Check if the item was already assigned to this machine in the previous iteration
                item_diameter = int(tref_items_dict[data['weights_name'][item]].Diameter * 1000)
                if item_diameter == most_common_diameter:
                    # Only create the variable if the diameter is consistent
                    x[item, mach] = solver.BoolVar(f"x_{item}_{mach}")
                    weight = item_weights[data["weights_name"][item]][mach]  # Direct lookup
                    # coeff = data["weights"][item] - ((cycle_times[data["weights_name"][item]][mach] * 100) / weight) \
                    #    if self.DataHandler.Criteria[1] else weight
                    coeff = (weight / (cycle_times[data["weights_name"][item]][mach] * 100)) * data["weights"][item] \
                        if self.DataHandler.Criteria[1] else weight
                    objective.SetCoefficient(x[item, mach], coeff)
                else:
                    continue

        # Constraints
        for i in data["all_items"]:
            solver.Add(sum(x[i, b] for b in data["all_bins"] if (i, b) in x) <= 1)

        for b in data["all_bins"]:
            solver.Add(
                sum(x[i, b] * data["weights"][i] for i in data["all_items"] if (i, b) in x) <= data["bin_capacities"][
                    b])
            solver.Add(sum(x[i, b] for i in data["all_items"] if (i, b) in x) <= data["output_capacities"][b])

        # Set objective and solve
        objective.SetMaximization()
        status = solver.Solve()

        # Collect results if optimal
        if status == pywraplp.Solver.OPTIMAL:
            results = {
                "total_packed_weight": 0,
                "total_objective_value": objective.Value(),
                "individual_weights": {b: [] for b in data["bins"]},
                "individual_weights_names": {b: [] for b in data["bins"]},
                "individual_weights_POs": {b: [] for b in data["bins"]},
                "allocated_exec_plans": {b: [] for b in data["bins"]},
            }

            for iter, b in enumerate(data["bins"]):
                bin_weight = 0
                for i in data["all_items"]:
                    if (i, iter) in x and x[i, iter].solution_value() > 0:
                        results["individual_weights"][b].append(data['weights'][i])
                        results["individual_weights_names"][b].append(data['weights_name'][i])
                        results["individual_weights_POs"][b].append(data['weights_PO'][i])
                        bin_weight += data["weights"][i]
                        results["allocated_exec_plans"][b].append(data["exec_plan_ids"][i])
                results["total_packed_weight"] += bin_weight
            return results
        return None

class TorcPandS():
    def __init__(self, DataHandler):
        self.DataHandler = DataHandler
        self.Machines, self.TorcItems, self.TrefItems = self.DataHandler.TorcMachines, self.DataHandler.TorcItems, self.DataHandler.TrefItems
        self.SetupTimesCache, self.CycleTimesCache, self.MaterialTypeCache, self.RoutingCache = (
            self.cacheSetupTimes(), self.cacheCycleTimes(), self.cacheMaterialTypes(), self.cacheRoutings())
        self.MachinePreviousPlanCoT, self.MachineObjFun = {}, {}
        self.InitialSolution, self.Operations = self.generateInitialSolution()
        self.Check = False
        self.LateOrders = self.simulatedAnnealing()

    def cacheSetupTimes(self):
        """Cache setup times as a dictionary for faster lookups."""
        return {(instance.FromMaterial, instance.ToMaterial): float(instance.SetupTime) for instance in
                self.DataHandler.SetupTimesByMaterial}

    def cacheCycleTimes(self):
        """Cache cycle times as a dictionary for faster lookups."""
        return {(routing.Machine, routing.Item): routing.CycleTime / 1000 for routing in self.DataHandler.Routings}

    def cacheMaterialTypes(self):
        """Cache material types as a dictionary for faster lookups."""
        return {torc_item.Name: torc_item.MaterialType for torc_item in self.TorcItems}

    def cacheRoutings(self):
        routings_cache = {}
        for routing in self.DataHandler.Routings:
            if routing.Item not in routings_cache:
                routings_cache[routing.Item] = []
            for machine in self.Machines:
                if machine.IsActive and routing.Machine == machine.MachineCode:
                    routings_cache[routing.Item].append(machine)
        return routings_cache

    def getSetupTime(self, prev_type, cur_type):
        return self.SetupTimesCache.get((prev_type, cur_type), 0.0)

    def getCycleTime(self, machine, item_name):
        return self.CycleTimesCache.get((machine, item_name), None)

    def getMaterialType(self, item_name):
        return self.MaterialTypeCache.get(item_name, None)
    
    def nextShiftStartTime(self, current_time, shift_start_times):
        for shift_start in shift_start_times:
            shift_start_dt = datetime.combine(current_time.date(), shift_start)
            if current_time < shift_start_dt:
                return shift_start_dt
        return datetime.combine(current_time.date() + timedelta(days=1), shift_start_times[0])

    def getPreviousPlanCoT(self, machine):
        """Get the Completion Time of the latest Execution Plan in the current machine"""
        shift_start_times = [time(0, 0), time(8, 0), time(16, 0)]

        with pyodbc.connect(self.DataHandler.ConnectionString) as conn, conn.cursor() as cursor:
            # Get latest execution plan for the machine
            cursor.execute(
                """SELECT TOP 1 ep.Item, ep.CompletionTime 
                   FROM ExecutionPlans ep 
                   JOIN Items i ON ep.Item COLLATE SQL_Latin1_General_CP1_CI_AS = i.Item 
                   WHERE i.Process = 'BUN' AND ep.Machine = ? 
                   ORDER BY CompletionTime DESC""", 
                (machine,)
            )
            result = cursor.fetchone()
            latest_ep_item, previous_plan_CoT = result if result else (None, None)
        
        # Determine start time
        start_time = max(previous_plan_CoT, self.DataHandler.CurrentTime) if previous_plan_CoT else self.DataHandler.CurrentTime
            
        return [latest_ep_item, self.nextShiftStartTime(start_time, shift_start_times)]

    def getBoMItems(self, bom_id):
        return [[item.ItemRelated, item.Quantity] for bom in self.DataHandler.BoMs if bom.id == bom_id for item in bom.BoMItems]

    def getItemST(self, ep, previous_plan_CoT, previous_item_CoT, used_eps, tref_item_CoT, update_STs):
        tref_latest_CoT = datetime.min
        prod_order_id = ep.ProductionOrder.id
        
        if update_STs:
            # Find the BOM ID, safely handling the case where it might not exist
            matching_exec_plans = [exec_plan for exec_plan in self.DataHandler.ExecutionPlans 
                                  if exec_plan.ItemRoot
                                  and exec_plan.ItemRoot.Name == ep.ItemRelated.Name 
                                  and exec_plan.ProductionOrder.id == ep.ProductionOrder.id]
            
            # If we found matching execution plans, proceed with BOM processing
            if matching_exec_plans:
                bom_id = matching_exec_plans[0].BoMId
                bom_items = self.getBoMItems(bom_id)
    
                for item, quantity in bom_items:
                    if Items.get_Item(item, self.DataHandler.Database).Process == "BUN":
                        break
                    for _ in range(quantity):
                        # Filter eligible execution plans with CoT greater than the last tref item CoT, if it exists
                        eligible_eps = [exec_plan for exec_plan in self.DataHandler.ExecutionPlans
                                       if prod_order_id == exec_plan.ProductionOrder.id
                                       and item == exec_plan.ItemRelated.Name
                                       and exec_plan.id not in used_eps
                                       and (tref_item_CoT.get(item) is None or exec_plan.CoT > tref_item_CoT[item])]
    
                        # Select the eligible plan with the minimum CoT that meets the required condition
                        if eligible_eps:
                            min_ep = min(eligible_eps, key=lambda x: x.CoT)
                            if min_ep.CoT > max(previous_plan_CoT or datetime.min, previous_item_CoT or datetime.min):
                                used_eps.append(min_ep.id)
                                tref_item_CoT[item] = min_ep.CoT
                                tref_latest_CoT = max(tref_latest_CoT or datetime.min, min_ep.CoT)
                            else:
                                break
            # If no matching execution plans found, tref_latest_CoT remains as datetime.min
        else:
            tref_latest_CoT = max(
                (tu.CoT for tu in self.DataHandler.TimeUnits for exec_plan in tu.ExecutionPlans
                if prod_order_id == exec_plan.ProductionOrder.id), default=self.DataHandler.CurrentTime.replace(hour=0, minute=0, second=0, microsecond=0)
            )
    
        # Return tref_latest_CoT's CoT if it exists; otherwise, max of previous_plan_CoT and previous_item_CoT
        return (
            max(tref_latest_CoT, previous_plan_CoT or datetime.min, previous_item_CoT or datetime.min)), used_eps, tref_item_CoT
    
    def getSTandCoT(self, CT, ST, setup_time):
        ST += timedelta(hours=setup_time) + timedelta(minutes=(CT * 0.08))
        CoT = ST + timedelta(minutes=CT)
        return ST, CoT

    def calculateTimes(self, machine, data, previous_item_CoT, previous_type, used_eps, tref_item_CoT, update_STs=False):
        current_type = self.getMaterialType(data[0])
        previous_plan_CoT = self.MachinePreviousPlanCoT[machine][1]
        CT = self.getCycleTime(machine, data[0]) * data[1].Quantity
        setup_time = self.getSetupTime(previous_type, current_type) if previous_type != current_type else 0.0
        ST, used_eps, tref_item_CoT = self.getItemST(data[1], previous_plan_CoT, previous_item_CoT, used_eps, tref_item_CoT,
                                                     update_STs)
        updated_ST, CoT = self.getSTandCoT(CT, ST, setup_time)
        return updated_ST, CoT, current_type, used_eps, tref_item_CoT

    def generateInitialSolution(self):
        '''Generates a randomized initial solution.'''

        def get_possible_machines(exec_plan):
            return [m for r in self.DataHandler.Routings if r.Item == exec_plan.ItemRelated.Name
                    for m in self.Machines if r.Machine == m.MachineCode]

        initial_solution = {machine.MachineCode: [] for machine in self.Machines if machine.IsActive}
        special_case_items = [ep.ItemRoot.Name for ep in self.DataHandler.ExecutionPlans if
                              ep.ItemRoot and ep.ItemRelated.Process == "BUN"]
        exec_plans = [ep for ep in self.DataHandler.ExecutionPlans if ep.ItemRelated.Process == "BUN" and ep.ItemRelated.Name
                      not in special_case_items]
        sorted_exec_plans = sorted(exec_plans, key=lambda x: x.ProductionOrder.DD)
        sorted_exec_plans.reverse()
        operations = {i + 1: ep for i, ep in enumerate(sorted_exec_plans)}

        product_batches = {}
        for op_number, exec_plan in operations.items():
            product_name = exec_plan.ItemRelated.Name
            prod_order_id = exec_plan.ProductionOrder.id
            product_key = (product_name, prod_order_id)
            if product_key not in product_batches:
                product_batches[product_key] = []
            product_batches[product_key].append(op_number)
                
        if self.DataHandler.Database == 'COFACTORY_GR':
            max_ct = 0
            for product_key, operation_numbers in product_batches.items():
                for op_number in operation_numbers:
                    exec_plan = operations[op_number]  # Get the exec_plan for the current operation number
                    possible_machines = get_possible_machines(exec_plan)
                    possible_machines.sort(
                        key=lambda machine: self.getCycleTime(machine.MachineCode, exec_plan.ItemRelated.Name))
                    for machine in possible_machines:
                        ct = self.getCycleTime(machine.MachineCode, exec_plan.ItemRelated.Name) * exec_plan.Quantity
                        max_ct = max(ct, max_ct)
            
            for product_key, operation_numbers in product_batches.items():
                op_n = operation_numbers[0]
                exec_plan = operations[op_n]
                possible_machines = get_possible_machines(exec_plan)
                possible_machines.sort(
                    key=lambda machine: self.getCycleTime(machine.MachineCode, exec_plan.ItemRelated.Name))
                current_index = 0  # Initialize persistent index outside the inner loop
                flag = False
                for machine in possible_machines:
                    ct_sum = 0
                    for i, op_number in enumerate(operation_numbers[current_index:]):  # Start from current_index
                        exec_plan = operations[op_number]
                        ct = self.getCycleTime(machine.MachineCode, exec_plan.ItemRelated.Name) * exec_plan.Quantity
                        ct_sum += ct
                        if ct_sum > max_ct:
                            current_index += i  # Update current_index to skip checked operations
                            break
                        machine_name = machine.MachineCode
                        initial_solution[machine_name].append(
                            (op_number, [exec_plan.ItemRelated.Name, exec_plan, 0, 0]))
                        # Check if all operations have been assigned
                        if current_index + i + 1 >= len(operation_numbers):
                            flag = True
                            break
                    if flag:
                        # Break out of machine loop if all operations have been assigned
                        break
                while current_index < len(operation_numbers) and not flag:
                    for machine in possible_machines:
                        if current_index >= len(operation_numbers):
                            break  # If all operations are assigned, stop
                        
                        op_number = operation_numbers[current_index]
                        exec_plan = operations[op_number]
                        machine_name = machine.MachineCode

                        # Assign only one operation per machine
                        initial_solution[machine_name].append(
                            (op_number, [exec_plan.ItemRelated.Name, exec_plan, 0, 0])
                        )

                        current_index += 1  # Update current_index to skip checked operations
                        if current_index >= len(operation_numbers): # Check if all operations have been assigned
                            break  
        else:
            for product_key, operation_numbers in product_batches.items():
                # Loop through all operation numbers for the given product_key
                for i, op_number in enumerate(operation_numbers):
                    exec_plan = operations[op_number]  # Get the exec_plan for the current operation number
                    possible_machines = get_possible_machines(exec_plan)

                    if possible_machines:
                        machine_count = len(possible_machines)
                        # Distribute the current operation across available machines
                        machine = possible_machines[i % machine_count]  # Rotate through machines in round-robin fashion
                        machine_name = machine.MachineCode

                        # Add the current exec_plan to the selected machine's schedule
                        initial_solution[machine_name].append(
                            (op_number, [exec_plan.ItemRelated.Name, exec_plan, 0, 0]))
                        
        self.MachinePreviousPlanCoT = {machine: self.getPreviousPlanCoT(machine) or None for machine in initial_solution}

        for machine, ops in initial_solution.items():
            used_eps = []
            tref_item_CoT = {}
            previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
            previous_item_CoT = None
            for op, data in ops:
                ST, CoT, current_type, used_eps, tref_item_CoT = self.calculateTimes(machine, data, previous_item_CoT,
                                                                                     previous_type, used_eps,
                                                                                     tref_item_CoT)
                # Ensure valid start and completion times
                data[2], data[3] = ST, CoT
                previous_item_CoT, previous_type = CoT, current_type
                
        return initial_solution, operations

    def objFun(self, solution, updated_machines=None):
        """Calculate the objective function value for the given solution. Objective - Minimize tardiness and penalize alternations."""

        def calculate_machine_objfun(machine, operations):
            tardiness_value, early_completion_value = 0, 0
            used_eps = []
            tref_item_CoT = {}

            if not operations:
                return 0, 0

            previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
            previous_item_CoT = last_item_name = None

            for _, (_, data) in enumerate(operations):
                current_item_name = data[1].ItemRelated.Name
                ST, CoT, current_type, used_eps, tref_item_CoT = self.calculateTimes(
                    machine, data, previous_item_CoT, previous_type, used_eps, tref_item_CoT
                )

                # Minimizing Tardiness
                Tardiness = max(CoT - data[1].ProductionOrder.DD, timedelta(0))
                tardiness_minutes = Tardiness.total_seconds() / 60
                tardiness_value += tardiness_minutes

                # Alternation penalty
                if last_item_name and last_item_name != current_item_name:
                    alternation_penalty = 4000

                    # Scale alternation penalty relative to the current tardiness
                    if tardiness_minutes > 0:
                        alternation_penalty_weight = min(0.5, tardiness_minutes / 1000)  # Dynamic weight
                    else:
                        alternation_penalty_weight = 0.1  # Minimum weight for no tardiness

                    alternation_penalty *= alternation_penalty_weight
                    tardiness_value += alternation_penalty

                # Early Completion Reward
                early_completion_time = (data[1].ProductionOrder.DD - CoT).total_seconds() / 60
                if early_completion_time > 0:  # Only count positive early completions
                    early_completion_value += early_completion_time

                data[2], data[3] = ST, CoT
                last_item_name = current_item_name
                previous_item_CoT, previous_type = CoT, current_type

            return tardiness_value, early_completion_value

        if updated_machines is None:
            total_tardiness_value = 0
            total_early_completion_value = 0
            for machine, operations in solution.items():
                tardiness, early_completion = calculate_machine_objfun(machine, operations)
                self.MachineObjFun[machine] = (tardiness, early_completion)
                total_tardiness_value += tardiness
                total_early_completion_value += early_completion
            return total_tardiness_value, total_early_completion_value, None

        machineObjFunValue = self.MachineObjFun.copy()

        total_tardiness_value = sum(
            machineObjFunValue[machine][0] for machine in machineObjFunValue if machine not in updated_machines
        )
        total_early_completion_value = sum(
            machineObjFunValue[machine][1] for machine in machineObjFunValue if machine not in updated_machines
        )

        for machine in updated_machines:
            tardiness, early_completion = calculate_machine_objfun(machine, solution[machine])
            machineObjFunValue[machine] = (tardiness, early_completion)
            total_tardiness_value += tardiness
            total_early_completion_value += early_completion

        return total_tardiness_value, total_early_completion_value, machineObjFunValue

    def machineMove(self, solution, op1, op2):
        '''Takes a solution dictionary, machine, and two operations op1, op2.
        Returns a new solution with op1 and op2 swapped within the same machine.
        '''
        solution_aux = {k: list(v) for k, v in solution.items()}

        def check_adjacent_items(op_index, operations):
            if 0 < op_index < len(operations) - 1:
                # Check if current and adjacent items have the same name
                item_names = [
                    operations[op_index - 1][1][1].ItemRelated.Name,
                    operations[op_index][1][1].ItemRelated.Name,
                    operations[op_index + 1][1][1].ItemRelated.Name
                ]
                return len(set(item_names)) == 1
            return False

        for machine, operations in solution.items():
            if not operations:
                continue
            indices = [i for i, op in enumerate(operations) if op[0] in (op1, op2)]
            if len(indices) == 2:
                op1_idx, op2_idx = indices
                # Avoid alternation if adjacent items are identical
                if check_adjacent_items(op1_idx, operations) or check_adjacent_items(op2_idx, operations):
                    return solution, None

                # Perform the swap
                solution_aux[machine][op1_idx], solution_aux[machine][op2_idx] = (
                    solution_aux[machine][op2_idx],
                    solution_aux[machine][op1_idx],
                )
                return solution_aux, machine
        return solution, None

    def machineSwitch(self, solution, op, machine):
        '''Takes a solution dictionary, operation, and machine.
        Returns a new solution with the operation assigned to the specified machine.
        '''
        solution_aux = {k: list(v) for k, v in solution.items()}
        # Find the machine containing the operation
                
        current_machine = next((m for m, ops in solution.items() if any(o[0] == op for o in ops)), None)

        # If the current machine is the same as the chosen one, we can't make the switch
        if machine.MachineCode == current_machine:
            return solution, None

        # Remove the operation from its current machine
        operation = next(o for o in solution[current_machine] if o[0] == op)
        solution_aux[current_machine].remove(operation)

        # Assign the operation to the specified machine at the end of its list
        solution_aux[machine.MachineCode].append(operation)

        return solution_aux, current_machine

    def simulatedAnnealing(self):
        '''Simulated Annealing algorithm implementation for optimizing the scheduling problem.'''
        # Parameters
        initial_temp = 500 * len(self.Operations)
        final_temp = 0.01
        max_iter_per_temp = 100
        alpha = 0.99

        # Initial solution and its objective value
        current_solution = self.InitialSolution
        current_tardiness, best_early_completion, _ = self.objFun(current_solution)
        best_solution = self.InitialSolution
        best_tardiness = current_tardiness

        temperature = initial_temp
        iter_total = no_improvement_iterations = 0
        attempted_moves = set()  # Track moves that don't improve the solution

        while temperature > final_temp:
            for _ in range(max_iter_per_temp):
                iter_total += 1
                op2 = machine_to_switch = None
                updated_machines = []
                # Randomly choose a move type (either machineMove or machineSwitch)
                if iter_total % 2 == 0:
                    op1, op2 = random.sample(list(self.Operations.keys()), 2)
                    # Skip move if already attempted
                    if ((op1, op2) in attempted_moves or (op2, op1) in attempted_moves or
                            self.Operations[op1].ItemRelated.Name == self.Operations[op2].ItemRelated.Name):
                        continue

                    candidate_solution, machine_to_move = self.machineMove(current_solution, op1, op2)
                    if machine_to_move:
                        updated_machines.append(machine_to_move)
                else:
                    op1 = random.choice(list(self.Operations.keys()))
                    routings = self.RoutingCache[self.Operations[op1].ItemRelated.Name]
                    machine_to_switch = random.choice(routings)

                    # Skip move if already attempted
                    if (op1, machine_to_switch.MachineCode) in attempted_moves:
                        continue

                    candidate_solution, machine_origin = self.machineSwitch(current_solution, op1,
                                                                            machine_to_switch)
                    if machine_origin:
                        updated_machines.extend([machine_origin, machine_to_switch.MachineCode])

                # Calculate the objective function of the candidate solution
                if not updated_machines:
                    if iter_total % 2 == 0:
                        attempted_moves.add((op1, op2))
                    else:
                        attempted_moves.add((op1, machine_to_switch.MachineCode))
                    continue

                candidate_tardiness, candidate_early_completion, candidate_machineObjValues = self.objFun(
                    candidate_solution, updated_machines)

                # Calculate the change in objective value 
                delta_tardiness = candidate_tardiness - current_tardiness

                # Acceptance condition: if candidate solution is better, accept it
                if delta_tardiness < 0:
                    current_solution = candidate_solution
                    current_tardiness = candidate_tardiness
                    self.MachineObjFun = candidate_machineObjValues
                    # Update the best solution found so far
                    if candidate_tardiness < best_tardiness or (
                            candidate_tardiness == best_tardiness and candidate_early_completion > best_early_completion
                    ):
                        best_solution = candidate_solution
                        best_tardiness = candidate_tardiness
                        best_early_completion = candidate_early_completion
                        no_improvement_iterations = 0  # Reset counter
                        attempted_moves.clear()  # Reset attempted moves on improvement
                        #print(
                        #    f"Iter {iter_total}: Best tardiness improved to {best_tardiness} with early completion {best_early_completion}")
                else:
                    # Accept worse solutions with a probability P
                    probability = math.exp(-delta_tardiness / temperature)
                    if random.random() < probability:
                        current_solution = candidate_solution
                        current_tardiness = candidate_tardiness
                        self.MachineObjFun = candidate_machineObjValues
                        no_improvement_iterations += 1
                        #print(f"Iter {iter_total}: Worse solution accepted with objValue {current_tardiness}")
                    else:
                        # Record unsuccessful move to avoid repeating it
                        if iter_total % 2 == 0:
                            attempted_moves.add((op1, op2))
                        else:
                            attempted_moves.add((op1, machine_to_switch.MachineCode))
                        no_improvement_iterations += 1

            # Cool down the temperature
            temperature *= alpha
        
        # Calculate max CoT for each machine and sort best_solution
        machine_max_CoT = {
            machine: max((data[3] for _, data in ops),
                         default=self.DataHandler.CurrentTime.replace(hour=0, minute=0, second=0, microsecond=0))
            for machine, ops in best_solution.items()
        }
        best_solution = dict(sorted(best_solution.items(), key=lambda x: machine_max_CoT[x[0]]))
        

        used_eps = []
        for machine, ops in best_solution.items():
            print(machine)
            if not ops:
                continue
            tref_item_CoT = {}
            previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
            previous_item_CoT = None
            for _, data in ops:
                print(data)
                ST, CoT, current_type, used_eps, tref_item_CoT = self.calculateTimes(machine, data, previous_item_CoT,
                                                                                     previous_type, used_eps,
                                                                                     tref_item_CoT,
                                                                                     update_STs=True)
                # Ensure valid start and completion times
                data[2], data[3] = ST, CoT
                previous_item_CoT, previous_type = CoT, current_type

        special_case = [ep.ItemRoot.Name for ep in self.DataHandler.ExecutionPlans if
                        ep.ItemRoot and ep.ItemRelated.Process == "BUN"]
        
        special_case_eps = [ep for ep in self.DataHandler.ExecutionPlans if
                            ep.ItemRelated.Process == "BUN" and ep.ItemRelated.Name
                            in special_case]
        
        if special_case_eps:
            used_eps, sc_eps_ST = [], {}
            for sc_ep in special_case_eps:
                last_BoM_item = None
                # Retrieve routings for the current special case item
                routings = self.RoutingCache[sc_ep.ItemRelated.Name]

                bom_id = next(
                    (exec_plan.BoMId for exec_plan in self.DataHandler.ExecutionPlans
                     if exec_plan.ItemRoot and exec_plan.ItemRoot.Name == sc_ep.ItemRelated.Name
                     and exec_plan.ProductionOrder.id == sc_ep.ProductionOrder.id),
                    None
                )

                bom_items = self.getBoMItems(bom_id)
                available_items = [
                    data for _, ops in best_solution.items()
                    for _, data in ops
                    if data[1].ProductionOrder.id == sc_ep.ProductionOrder.id
                       and data[1].ItemRoot
                       and sc_ep.ItemRelated.Name == data[1].ItemRoot.Name
                       and sc_ep.Quantity == data[1].Quantity
                ]

                for _, quantity in bom_items:
                    for _ in range(quantity):
                        eligible_eps = [data for data in available_items if data[1].id not in used_eps]
                        if eligible_eps:
                            min_ep = min(eligible_eps, key=lambda x: x[3])  # Use CoT
                            used_eps.append(min_ep[1].id)
                            last_BoM_item = min_ep

                if last_BoM_item:
                    # Find the machine where the last item is located
                    sc_machine = None
                    sc_eps_ST[sc_ep.id] = last_BoM_item[3]
                    for machine, ops in best_solution.items():
                        if machine in routings and any(data[1].id == last_BoM_item[1].id for _, data in ops):
                            sc_machine = machine
                            break

                    if sc_machine is None:
                        sc_machine = min(
                            routings,
                            key=lambda m: self.getCycleTime(m.MachineCode, sc_ep.ItemRelated.Name)
                        )
                        CT = self.getCycleTime(sc_machine.MachineCode, sc_ep.ItemRelated.Name) * sc_ep.Quantity
                        ST = last_BoM_item[3] + timedelta(minutes=(CT * 0.08))
                        CoT = ST + timedelta(minutes=CT)

                        target_ops = best_solution[sc_machine.MachineCode]
                        if target_ops:
                            candidates = [i for i, (_, data) in enumerate(target_ops) if data[3] <= last_BoM_item[3]]
                            if candidates:
                                position = candidates[-1]  # Pegamos o último índice válido
                                target_ops.insert(position + 1, (None, [sc_ep.ItemRelated.Name, sc_ep, ST, CoT]))
                            else:
                                # Se não houver candidatos válidos, insere na primeira posição
                                target_ops.insert(0, (None, [sc_ep.ItemRelated.Name, sc_ep, ST, CoT]))
                    else:
                        CT = self.getCycleTime(sc_machine.MachineCode, sc_ep.ItemRelated.Name) * sc_ep.Quantity
                        ST = last_BoM_item[3] + timedelta(minutes=(CT * 0.08))
                        CoT = ST + timedelta(minutes=CT)
                        target_ops = best_solution[sc_machine.MachineCode]
                        position = next(
                            i for i, (_, data) in enumerate(target_ops) if data[1].id == last_BoM_item[1].id)
                        target_ops.insert(position + 1, (None, [sc_ep.ItemRelated.Name, sc_ep, ST, CoT]))

            used_eps = []
            for machine, ops in best_solution.items():
                print(machine)
                if not ops:
                    continue
                tref_item_CoT = {}
                previous_type = next((item.MaterialType for item in self.DataHandler.Items if item.Name == self.MachinePreviousPlanCoT[machine][0]), None)
                previous_item_CoT = None
                for _, data in ops:
                    print(data)
                    CT = self.getCycleTime(machine, data[0]) * data[1].Quantity
                    ST, CoT, current_type, used_eps, tref_item_CoT = self.calculateTimes(machine, data, previous_item_CoT,
                                                                                         previous_type, used_eps,
                                                                                         tref_item_CoT, update_STs=True)

                    if data[1].id in sc_eps_ST:
                        ST = max(ST, (sc_eps_ST[data[1].id] + timedelta(minutes=(CT * 0.08))))
                        CoT = ST + timedelta(minutes=CT)
                    # Ensure valid start and completion times
                    data[2], data[3] = ST, CoT
                    previous_item_CoT, previous_type = CoT, current_type
        
        printed_prod_orders = set()
        printed_prod_names = []
        for machine, operations in best_solution.items():
            for op in operations:
                _, details = op
                product_name, exec_plan, start_time, completion_time = details

                exec_plan = next(
                    (exec_plan_ for exec_plan_ in self.DataHandler.ExecutionPlans if exec_plan_.id == exec_plan.id), None)

                # Update execution plan's timing and machine
                exec_plan.ST = start_time
                exec_plan.CoT = completion_time
                exec_plan.Machine = machine

                # Find the production order associated with this execution plan
                prod_order = next((prod_order for prod_order in self.DataHandler.ProductionOrders if
                                   prod_order.id == exec_plan.ProductionOrder.id), None)

                # Update production order's completion time
                if not prod_order.CoT or exec_plan.CoT > prod_order.CoT:
                    prod_order.CoT = exec_plan.CoT

                # Only print the production order if it hasn't been printed yet:
                if prod_order.CoT > prod_order.DD and prod_order.id not in printed_prod_orders:
                    print(f"Ordem de produção {prod_order.id} ({product_name}) não será entregue a tempo.")

                    # Mark this production order as printed
                    printed_prod_orders.add(prod_order.id)
                    printed_prod_names.append(product_name)
                    
        return printed_prod_names
        

