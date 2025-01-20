import numpy as np
from datetime import datetime, timedelta, time
import time as tm
import pyodbc
from openpyxl import Workbook, load_workbook

class TimeUnit:
    id = 0
    instances = []
    new_instances = []
    def __init__(self, Machine):
        TimeUnit.id += 1
        self.id = TimeUnit.id
        self.Name = f"timeUnit_{TimeUnit.id}"
        TimeUnit.new_instances.append(self)
        self.Machine = Machine
        self.ExecutionPlans = [] #Not inserted into the DB
        self.ST = 0
        self.CoT = 0

    @classmethod
    def clear_instances(cls):
        cls.instances.clear()
        cls.id = 0
    
    @classmethod
    def clear_new_instances(cls):
        cls.new_instances.clear()
        cls.id = 0

    def calculate_average_due_date(self):
        """Organize the Products by Due Date"""
        due_dates = [exec_plan.ProductionOrder.DD for exec_plan in self.ExecutionPlans]
        if due_dates:
            seconds = [tm.mktime(d.timetuple()) for d in due_dates]
            avg_due_date = datetime.fromtimestamp(np.mean(seconds))
            return avg_due_date
        else:
            return None

    def get_average_diameter(self):
        diameters = [int(Items.get_Item(ep.ItemRelated.Name).Diameter * 1000) for ep in self.ExecutionPlans if
                     Items.get_Item(ep.ItemRelated.Name)]
        if diameters:
            return np.mean(diameters)
        else:
            return float('inf')

    def get_primary_material_type(self):
        """Determine the primary material type among ExecutionPlans."""
        material_types = {ep.ItemRelated.MaterialType for ep in self.ExecutionPlans}
        if material_types:
            return sorted(material_types)[0]  # Assuming a sorted order can determine primary type
        return None

    def get_average_weight(self):
        """Get the average weight for execution plans with the same due date."""
        weights = [exec_plan.ProductionOrder.Weight for exec_plan in self.ExecutionPlans]
        if weights:
            return np.mean(weights)
        return float('inf')

    def calculate_time(self, TU_ST, previous_TU, connection_string, current_time):
        shift_start_times = [time(0, 0), time(8, 0), time(16, 0)]  # Midnight, 8 AM, 4 PM

        def start_time():
            with pyodbc.connect(connection_string) as conn:
                with conn.cursor() as cursor:
                    # Check if ExecutionPlans is populated
                    cursor.execute("SELECT COUNT(*) FROM TimeUnits WHERE Machine = ?", (self.Machine,))
                    row_count = cursor.fetchone()[0]

                    # Check if the table is empty
                    if row_count != 0:
                        cursor.execute(
                            "SELECT MAX(CompletionTime) AS MaxCompletionTime FROM TimeUnits WHERE Machine = ?",
                            (self.Machine,)
                        )
                        latest_ep_CoT = cursor.fetchone()[0]  # Fetch the first element of the result
                    else:
                        latest_ep_CoT = None

            start_time = latest_ep_CoT if latest_ep_CoT and latest_ep_CoT > current_time else current_time

            return next_shift_start(start_time)

        def next_shift_start(current_time):
            for shift_start in shift_start_times:
                shift_start_dt = datetime.combine(current_time.date(), shift_start)
                if current_time < shift_start_dt:
                    return shift_start_dt
            return datetime.combine(current_time.date() + timedelta(days=1), shift_start_times[0])

        # Determine start time (ST)
        if previous_TU:
            previous_type = previous_TU.ExecutionPlans[0].ItemRelated.MaterialType
            current_type = self.ExecutionPlans[0].ItemRelated.MaterialType
            setup_time = next(
                (float(instance.SetupTime) for instance in SetupTimesByMaterial.instances
                 if instance.FromMaterial == previous_type and instance.ToMaterial == current_type), 0.0)
            self.ST = previous_TU.CoT + timedelta(hours=setup_time) if setup_time else previous_TU.CoT
        else:
            if TU_ST is None:
                self.ST = start_time()
            else:
                calculated_ST = start_time()
                if calculated_ST > TU_ST:
                    self.ST = calculated_ST
                else:
                    self.ST = TU_ST

        # Get max completion time (CoT)
        max_CT = max(
            (next((routing.CycleTime / 1000) for routing in Routings.instances
                  if routing.Item == exec_plan.ItemRelated.Name and routing.Machine == self.Machine)
             * exec_plan.Quantity) for exec_plan in self.ExecutionPlans
        )
        self.ST += timedelta(minutes=(max_CT * 0.16))
        self.CoT = self.ST + timedelta(minutes=max_CT)

class BoM:
    id = 0
    instances = []
    def __init__(self, ItemRoot, BoMQuantity, BoMQuantityUnit, Revision, Default):
        BoM.id += 1
        self.id = BoM.id
        BoM.instances.append(self)
        self.ItemRoot = ItemRoot
        self.BoMQuantity = BoMQuantity
        self.BoMQuantityUnit = BoMQuantityUnit
        self.BoMItems = []
        self.Revision = Revision
        self.Default = Default

    def add_BoM_items(self, *args):
        self.BoMItems.extend(args)

class BoMItem:
    id = 0
    instances = []
    def __init__(self, ItemRoot, ItemRelated, Quantity, NetQuantity, NetQuantityUnit):
        BoMItem.id += 1
        self.id = BoMItem.id
        BoMItem.instances.append(self)
        self.ItemRoot = ItemRoot
        self.ItemRelated = ItemRelated
        self.NetQuantity = NetQuantity
        self.NetQuantityUnit = NetQuantityUnit
        self.Quantity = Quantity

class ProductionOrder:
    id = 0
    instances = []
    def __init__(self, Product, Quantity, DD, Weight):
        ProductionOrder.id += 1
        self.id = ProductionOrder.id
        self.Name = f"Operation_{ProductionOrder.id}"
        ProductionOrder.instances.append(self)
        self.Product = Product
        self.Quantity = Quantity
        self.DD = DD
        self.ST = 0
        self.CoT = 0
        self.Weight = Weight #This field will not be placed in the DB

    @classmethod
    def clear_instances(cls):
        cls.instances.clear()  # Clears all instances from the list
        cls.id = 0  # Optionally reset the id counter if needed

    def delete(self):
        """Delete the ProductionOrder"""
        if self in ProductionOrder.instances:
            ProductionOrder.instances.remove(self)

class ExecutionPlan:
    id = 0
    instances = []
    new_instances = []
    def __init__(self, ItemRoot, ItemRelated, Quantity, BoMId, ProductionOrder):
        ExecutionPlan.id += 1
        self.id = ExecutionPlan.id
        ExecutionPlan.new_instances.append(self)
        self.ItemRoot = ItemRoot
        self.ItemRelated = ItemRelated
        self.Quantity = Quantity
        self.Machine = None
        self.Position = None
        self.ProductionOrder = ProductionOrder
        self.ST = 0
        self.CoT = 0
        self.BoMId = BoMId #Not inserted into the DB

    @classmethod
    def clear_instances(cls):
        cls.instances.clear()  # Clears all instances from the list
        cls.id = 0  # Optionally reset the id counter if needed

    @classmethod
    def clear_new_instances(cls):
        cls.new_instances.clear()  # Clears all instances from the list
        cls.id = 0  # Optionally reset the id counter if needed

    @classmethod
    def remove_by_id(cls, target_id):
        cls.new_instances = [instance for instance in cls.new_instances if instance.id != target_id]

class Machines:
    instances = []
    def __init__(self, MachineCode, Input, Output, RunningTimeFactor):
        self.MachineCode = MachineCode
        Machines.instances.append(self)
        self.Input = Input
        self.Output = Output
        self.RunningTimeFactor = RunningTimeFactor
        self.IsActive = True
        
    @classmethod
    def clear_instances(cls):
        cls.instances.clear()
        cls.id = 0

class Routings:
    instances = []
    def __init__(self, Item, Machine, CycleTime, Weight):
        self.Item = Item
        Routings.instances.append(self)
        self.Machine = Machine
        self.CycleTime = CycleTime
        self.Weight = Weight

class Items:
    instances = []
    def __init__(self, Name, MaterialType, Unit, Input, Diameter, Process, OrderIncrement):
        self.Name = Name
        Items.instances.append(self)
        self.MaterialType = MaterialType
        self.Unit = Unit
        self.Process = Process
        self.Input = Input if Input is not None else 0
        self.Diameter = Diameter
        self.Category = None
        self.OrderIncrement = OrderIncrement

    @classmethod
    def get_Item(cls, name):
        for instance in cls.instances:
            if instance.Name == name:
                return instance
        return None

class SetupTimesByMaterial:
    instances = []
    def __init__(self, FromMaterial, ToMaterial, SetupTime):
        self.FromMaterial = FromMaterial
        SetupTimesByMaterial.instances.append(self)
        self.ToMaterial = ToMaterial
        self.SetupTime = SetupTime

class Stock:
    instances = []
    def __init__(self, Warehouse, Item, StockAvailable, StockAllocated, StockEconomic):
        self.Warehouse = Warehouse
        Stock.instances.append(self)
        self.Item = Item
        self.StockAvailable = StockAvailable
        self.StockAllocated = StockAllocated
        self.StockEconomic = StockEconomic

class InputData:
    def __init__(self, database, connection_string):
        self.Database, self.ConnectionString, self.CurrentTime = database, connection_string, None
        self.RODMachines, self.TorcMachines, self.TrefMachines, self.RODItems, self.TorcItems, self.TrefItems = None, None, None, None, None, None
        self.RODSolution = None
        self.Criteria = {}

    def getInputBoMs(file_name):
        item_root_boms = {}
        Extrusion_Input = load_workbook(file_name)
        Extrusion_Input_Active = Extrusion_Input.active
        unique_product_names = set()
        for row in Extrusion_Input_Active.iter_rows(min_row=2, values_only=True):
            product_name = row[0]
            item_root = Items.get_Item(product_name)
            if item_root:
                if product_name not in unique_product_names:
                    unique_product_names.add(product_name)
                for bom in BoM.instances:
                    if bom.ItemRoot == item_root.Name:
                        for BoM_Item in bom.BoMItems:
                            item_related = Items.get_Item(BoM_Item.ItemRelated)
                            if item_related and item_related.Process == "BUN" and item_related.Name not in unique_product_names:
                                unique_product_names.add(item_related.Name)
        for item_root in unique_product_names:
            match_count = 0  # Track the number of BoMs for this root Item
            item_root_boms[item_root] = []
            for bom in BoM.instances:
                if bom.ItemRoot == item_root:
                    match_count += 1
                    bom_items = []
                    # Add each BoM to the bom_items list
                    for BoM_Item in bom.BoMItems:
                        item_related = Items.get_Item(BoM_Item.ItemRelated)
                        for _ in range(BoM_Item.Quantity):
                            bom_items.append(item_related.Name)
                    item_root_boms[item_root].append(bom_items)
            # If match_count <= 1, then it means root Item only has one BoM, so it is removed from item_root_boms
            if match_count <= 1:
                item_root_boms.pop(item_root, None)

        return item_root_boms

    def checkStock(self, product_name, qty):
        with pyodbc.connect(self.ConnectionString) as conn:  # Opens the connection
            with conn.cursor() as cursor:  # Opens the cursor
                # Summing all relevant records
                cursor.execute(
                    "SELECT SUM(QuantityOrdered) FROM ProductionOrders "
                    "WHERE OrderStatus NOT IN ('4', '6') AND Item = ?", (product_name,)
                )

                result = cursor.fetchone()[0]  # Fetch the sum result
                # If the result is None (no records found), set stock to 0
                if result is not None:
                    item_stock = result  # This will contain the sum of the values
                else:
                    item_stock = 0

        for instance in Stock.instances:
            if instance.Item == product_name:
                if (instance.StockAvailable + item_stock) > 0:
                    if (instance.StockAvailable + item_stock) >= qty:
                        instance.StockAvailable -= qty
                        return 0
                    else:
                        qty -= instance.StockAvailable
                        instance.StockAvailable = 0
        return qty

    def createExecPlans(self, main_item, prod_order):
        no_routings = []
        def if_routing_exists(item_name, machines):
            """Check if there is a valid routing for the given item and machine list."""
            return any(routing.Item == item_name and routing.Machine in machines for routing in Routings.instances)

        def create_eps(bom, quantity, prod_order, first_iter):
            """Create ExecutionPlans for the main item and all its BOM dependencies."""
            if first_iter and if_routing_exists(main_item.Name, machines_Torc):
                ExecutionPlan(None, main_item, float(quantity), None, prod_order)
            elif not if_routing_exists(main_item.Name, machines_Torc):
                no_routings.append(main_item.Name)
            for BoM_Item in bom.BoMItems:
                item = Items.get_Item(BoM_Item.ItemRelated)
                production_qty = (BoM_Item.NetQuantity * quantity) / bom.BoMQuantity
                if item.Process == "BUN":
                    # new_prod_order = ProductionOrder(item, quantity, prod_order.DD, prod_order.Weight)
                    for _ in range(BoM_Item.Quantity):
                        if if_routing_exists(item.Name, machines_Torc):
                            ExecutionPlan(main_item, item, float(production_qty), bom.id, prod_order)
                        else:
                            no_routings.append(item.Name)
                        for second_bom in BoM.instances:
                            if second_bom.ItemRoot == item.Name:
                                for BoM_Item in second_bom.BoMItems:
                                    tref_item = Items.get_Item(BoM_Item.ItemRelated)
                                    for _ in range(BoM_Item.Quantity):
                                        sub_production_qty = (BoM_Item.NetQuantity * quantity) / second_bom.BoMQuantity
                                        if if_routing_exists(tref_item.Name, machines_Tref):
                                            ExecutionPlan(item, tref_item, float(sub_production_qty), second_bom.id,
                                                          prod_order)
                                        else:
                                            no_routings.append(tref_item.Name)
                else:
                    for _ in range(BoM_Item.Quantity):
                        if if_routing_exists(item.Name, machines_Tref):
                            ExecutionPlan(main_item, item, float(production_qty), bom.id, prod_order)
                        else:
                            no_routings.append(item.Name)

        machines_Torc = [machine.MachineCode for machine in self.TorcMachines]
        machines_Tref = [machine.MachineCode for machine in self.TrefMachines]

        order_increment = main_item.OrderIncrement
        total_qty, remainder_qty = divmod(prod_order.Quantity, order_increment)

        for _ in range(int(total_qty)):
            first_iteration = True
            for bom in BoM.instances:
                if bom.ItemRoot == main_item.Name:
                    create_eps(bom, order_increment, prod_order, first_iteration)
                    if first_iteration:
                        first_iteration = False

        if remainder_qty > 0:
            first_iteration = True
            for bom in BoM.instances:
                if bom.ItemRoot == main_item.Name:
                    create_eps(bom, remainder_qty, prod_order, first_iteration)
                    if first_iteration:
                        first_iteration = False

        return no_routings

    def createRemainingExecPlans(self, PT_Settings):
        Tref_items, ROD_items = {}, {}

        for TU in TimeUnit.new_instances:
            for exec_plan in TU.ExecutionPlans:
                item_name = exec_plan.ItemRelated.Name
                Tref_items[item_name] = round(Tref_items.get(item_name, 0) + exec_plan.Quantity)

        for tref_name in Tref_items:
            tref_item = Items.get_Item(tref_name)
            for bom in BoM.instances:
                if bom.ItemRoot == tref_item.Name:
                    for BoM_Item in bom.BoMItems:
                        ROD_item = Items.get_Item(BoM_Item.ItemRelated)
                        for _ in range(tref_item.Input):
                            prod_qty = float(self.checkStock(tref_item.Name, ROD_item.OrderIncrement)
                                             if self.Criteria[3] else ROD_item.OrderIncrement)
                            if PT_Settings:
                                prod_order = next((exec_plan.ProductionOrder for exec_plan in ExecutionPlan.new_instances
                                                   if tref_item.Name == exec_plan.ItemRelated.Name))
                                if prod_qty != 0:
                                    ExecutionPlan(tref_item, ROD_item, ROD_item.OrderIncrement, bom.id,
                                                  prod_order)
                            ROD_items[ROD_item.Name] = ROD_items.get(ROD_item.Name, 0) + prod_qty

    def readDBData(self):
        def fetch_data(queries):
            data = {}
            connection = None
            try:
                connection = pyodbc.connect(self.ConnectionString)
                cursor = connection.cursor()
                for query_key, query in queries.items():
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    data[query_key] = rows
                cursor.close()
            except pyodbc.Error as ex:
                print(f'Error: {ex}')
            finally:
                connection.close()
            return data

        def process_bom_data(rows, default):
            bom_dict = {}

            for row in rows:
                main_item = row[0]
                item = row[4] if default else row[5]
                quantity = row[1] if default else row[2]
                quantity_unit = row[2] if default else row[3]
                net_quantity = row[5] if default else row[6]
                net_quantity_unit = row[6] if default else row[7]
                revision = None if default else row[1]

                if main_item not in bom_dict:
                    bom_dict[main_item] = {
                        "BoMQuantity": quantity,
                        "BoMQuantityUnit": quantity_unit,
                        "items": {} if default else {},
                        "revisions": {} if not default else None,
                    }

                container = bom_dict[main_item]["items"] if default else bom_dict[main_item]["revisions"]
                if not default:
                    if revision not in container:
                        container[revision] = {}
                    container = container[revision]

                if item not in container:
                    container[item] = {
                        "NetQuantity": net_quantity,
                        "NetQuantityUnit": net_quantity_unit,
                        "count": 0
                    }

                container[item]["count"] += 1

            return bom_dict

        def create_bom_objects(bom_dict, default):
            for main_item, bom_data in bom_dict.items():
                if default:
                    # Create a single BoM object for the default case
                    bom = BoM(
                        ItemRoot=main_item,
                        BoMQuantity=bom_data["BoMQuantity"],
                        BoMQuantityUnit=bom_data["BoMQuantityUnit"],
                        Revision=None,
                        Default=default
                    )
                    bom_items = [
                        BoMItem(
                            ItemRoot=main_item,
                            ItemRelated=item,
                            Quantity=item_data["count"],
                            NetQuantity=item_data["NetQuantity"],
                            NetQuantityUnit=item_data["NetQuantityUnit"]
                        )
                        for item, item_data in bom_data["items"].items()
                    ]
                    bom.add_BoM_items(*bom_items)

                else:
                    # Create a separate BoM object for each revision in the non-default case
                    for revision, items in bom_data["revisions"].items():
                        bom = BoM(
                            ItemRoot=main_item,
                            BoMQuantity=bom_data["BoMQuantity"],
                            BoMQuantityUnit=bom_data["BoMQuantityUnit"],
                            Default=default,
                            Revision=revision
                        )
                        bom_items = [
                            BoMItem(
                                ItemRoot=main_item,
                                ItemRelated=item,
                                Quantity=item_data["count"],
                                NetQuantity=item_data["NetQuantity"],
                                NetQuantityUnit=item_data["NetQuantityUnit"]
                            )
                            for item, item_data in items.items()
                        ]
                        bom.add_BoM_items(*bom_items)

        def create_routing_objects(rows):
            for row in rows:
                main_item, machine, cycle_time, weight = row
                Routings(main_item, machine, cycle_time, int(weight))

        def create_items_objects(rows):
            for row in rows:
                main_item, input, diameter, unit, order_increment, process, material_type = row
                Items(main_item, material_type, unit, input, round(diameter, 3), process, order_increment)

        def create_machines_objects(rows):
            for row in rows:
                main_item, output, input, RT = row
                if self.Database == 'COFACTORY_PT' and main_item in {'MDW002', 'ROD004'}:
                    continue
                Machines(main_item, input, output, RT)

        def create_setup_times_objects(rows):
            for row in rows:
                from_material, to_material, setup_time = row
                SetupTimesByMaterial(from_material, to_material, setup_time)

        def create_stock_objects(rows):
            for row in rows:
                warehouse, item, stock_available, stock_allocated, stock_economic = row
                Stock(warehouse, item, stock_available, stock_allocated, stock_economic)

        def create_timeunits_objects(rows):
            for row in rows:
                time_unit_id, machine_code, st, cot = row
                tu_instance = TimeUnit(machine_code)
                tu_instance.id = time_unit_id
                tu_instance.ST = st
                tu_instance.CoT = cot
                tu_instance.instances.append(tu_instance)

        def create_executionplans_objects(rows):
            for row in rows:
                exec_plan_id, main_item_name, item_name, quantity, machine_code, prod_order_id, time_unit_position, st, cot = row

                item_root = Items.get_Item(
                    main_item_name) if main_item_name else None
                item_related = Items.get_Item(item_name)

                exec_plan = ExecutionPlan(item_root, item_related, quantity, None, prod_order_id)
                exec_plan.id = exec_plan_id
                exec_plan.Machine = machine_code
                exec_plan.Position = time_unit_position
                exec_plan.ST = st
                exec_plan.CoT = cot
                exec_plan.instances.append(exec_plan)

        def create_timeunit_executionplans_objects(rows):
            for row in rows:
                time_unit_id, execution_plan_id = row
                time_unit_instance = next((tu for tu in TimeUnit.instances if tu.id == time_unit_id), None)
                exec_plan_instance = next((ep for ep in ExecutionPlan.instances if ep.id == execution_plan_id), None)

                if exec_plan_instance:
                    time_unit_instance.ExecutionPlans.append(exec_plan_instance)

        queries = {
            "boms": "SELECT Boms.MainItem, Boms.Quantity, Boms.QuantityUnit, Boms.Position, Boms.Item, Boms.NetQuantity, Boms.NetQuantityUnit FROM Boms JOIN Items i ON MainItem = i.Item WHERE i.Process IN ('ROD', 'MDW', 'BUN')",
            "eboms": "SELECT Eboms.MainItem, Eboms.Revision, Eboms.Quantity, Eboms.QuantityUnit, Eboms.Position, Eboms.Item, Eboms.NetQuantity, Eboms.NetQuantityUnit FROM Eboms JOIN Items i ON MainItem = i.Item WHERE i.Process IN ('ROD', 'MDW', 'BUN')",
            "routings": "SELECT MainItem, RoutingCode, CycleTime, Priority FROM Routings JOIN Items i ON MainItem = i.Item WHERE i.Process IN ('ROD', 'MDW', 'BUN') AND (MainItem LIKE 'B%' OR MainItem LIKE 'D%')",
            "machines": "SELECT MachineCode, WindersCount, PayoffsCount, RunningTimeFactor FROM Machines WHERE (MachineCode LIKE 'BUN0%' OR MachineCode LIKE 'BMC%' OR MachineCode LIKE 'MDW0%' OR MachineCode LIKE 'ROD0%')",
            "items": "SELECT Item, StrandsNumber, StrandsDiameter, Unit, OrderIncrement, Process, MaterialType FROM Items",
            "setup_times": "SELECT FromMaterial, ToMaterial, SetupTime FROM SetupTimesByMaterial",
            "stock": "SELECT Warehouse, Item, StockAvailable, StockAllocated, StockEconomic FROM Stock",
            "timeunits": "SELECT id, Machine, StartTime, CompletionTime FROM TimeUnits",
            "execution_plans": "SELECT id, MainItem, Item, Quantity, Machine, ProductionOrder, Position, StartTime, CompletionTime FROM ExecutionPlans",
            "timeunit_executionplans": "SELECT tep.TimeUnitId, tep.ExecutionPlanId FROM TimeUnitExecutionPlans tep JOIN TimeUnits tu ON tep.TimeUnitId = tu.id JOIN ExecutionPlans ep ON tep.ExecutionPlanId = ep.id"
        }

        data = fetch_data(queries)

        # Process and create objects for each type of data
        bom_dict = process_bom_data(data["boms"], True)
        create_bom_objects(bom_dict, True)

        ebom_dict = process_bom_data(data["eboms"], False)
        create_bom_objects(ebom_dict, False)

        create_items_objects(data["items"])

        create_machines_objects(data["machines"])

        create_routing_objects(data["routings"])

        create_setup_times_objects(data["setup_times"])

        create_stock_objects(data["stock"])

        create_timeunits_objects(data["timeunits"])

        create_executionplans_objects(data["execution_plans"])

        create_timeunit_executionplans_objects(data["timeunit_executionplans"])

        self.RODMachines, self.TorcMachines, self.TrefMachines, self.RODItems, self.TorcItems, self.TrefItems = self.getSpecificData()

    def writeExcelData(self, PT_Settings):
        wb = Workbook()
        ws = wb.active

        # Add a header row
        ws.append([
            "Factory", "Routing", "Production Order ID", "Item", "Quantity",
            "Unit", "PO Start Time", "PO End Time", "Requested Delivery Date"
        ])

        if PT_Settings:
            grouped_plans = {}

            # Group execution plans by Machine, ItemRelated.Name, and ProductionOrder.DD
            for exec_plan in ExecutionPlan.new_instances:
                if exec_plan.ItemRoot and exec_plan.ItemRelated.Process == 'BUN':
                    # Find the main execution plan related to the current execution plan's item root
                    main_ep = next(
                        (ep for ep in ExecutionPlan.new_instances if
                         exec_plan.ItemRoot.Name == ep.ItemRelated.Name and ep.ItemRoot is None),
                        None
                    )
                    prod_order = main_ep.ProductionOrder if main_ep else exec_plan.ProductionOrder
                else:
                    prod_order = exec_plan.ProductionOrder

                # Use prod_order in the grouping key
                key = (exec_plan.Machine, exec_plan.ItemRelated.Name, prod_order.DD, exec_plan.ItemRelated.Process)

                if key not in grouped_plans:
                    grouped_plans[key] = {
                        'quantity': exec_plan.Quantity,
                        'earliest_ST': exec_plan.ST,
                        'latest_CoT': exec_plan.CoT,
                        'unit': exec_plan.ItemRelated.Unit,
                        'prod_order': prod_order
                    }
                else:
                    grouped_plans[key]['quantity'] += exec_plan.Quantity
                    grouped_plans[key]['earliest_ST'] = min(grouped_plans[key]['earliest_ST'], exec_plan.ST)
                    grouped_plans[key]['latest_CoT'] = max(grouped_plans[key]['latest_CoT'], exec_plan.CoT)

            # Create the ws entries
            for (machine, item_name, dd, process), plan_data in sorted(grouped_plans.items(), key=lambda x: x[0][3]):
                ws.append([
                    "122",
                    machine,
                    plan_data['prod_order'].id,
                    item_name,
                    plan_data['quantity'],
                    plan_data['unit'],
                    plan_data['earliest_ST'],
                    plan_data['latest_CoT'],
                    dd
                ])
        else:
            grouped_plans = {}

            # Group execution plans by Machine, ItemRelated.Name, and ProductionOrder.DD
            for exec_plan in ExecutionPlan.new_instances:
                # Grouping logic (similar to the if condition)
                key = (exec_plan.Machine, exec_plan.ItemRelated.Name, exec_plan.ProductionOrder.DD, exec_plan.ItemRelated.Process)

                if key not in grouped_plans:
                    grouped_plans[key] = {
                        'quantity': exec_plan.Quantity,
                        'earliest_ST': exec_plan.ST,
                        'latest_CoT': exec_plan.CoT,
                        'unit': exec_plan.ItemRelated.Unit,
                        'prod_order': exec_plan.ProductionOrder
                    }
                else:
                    grouped_plans[key]['quantity'] += exec_plan.Quantity
                    grouped_plans[key]['earliest_ST'] = min(grouped_plans[key]['earliest_ST'], exec_plan.ST)
                    grouped_plans[key]['latest_CoT'] = max(grouped_plans[key]['latest_CoT'], exec_plan.CoT)

            # Create the ws entries
            for (machine, item_name, dd, process), plan_data in sorted(grouped_plans.items(), key=lambda x: x[0][3]):
                ws.append([
                    "125",
                    machine,
                    plan_data['prod_order'].id,
                    item_name,
                    plan_data['quantity'],
                    plan_data['unit'],
                    plan_data['earliest_ST'],
                    plan_data['latest_CoT'],
                    dd
                ])

        # Save the workbook to a file
        wb.save("OUTPUT_MetalPlan.xlsx")

        wb = Workbook()
        ws = wb.active

        # Add a header row
        ws.append([
            "Factory", "Routing", "Production Order ID", "Item", "Quantity",
            "Unit", "PO Start Time", "PO End Time", "Requested Delivery Date"
        ])

        # Write the data to the worksheet
        if PT_Settings:
            for exec_plan in ExecutionPlan.new_instances:
                if exec_plan.ItemRoot and exec_plan.ItemRelated.Process == 'BUN':
                    # Find the main execution plan related to the current execution plan's item root
                    main_ep = next(
                        (ep for ep in ExecutionPlan.new_instances if
                         exec_plan.ItemRoot.Name == ep.ItemRelated.Name and ep.ItemRoot is None),
                        None
                    )
                    prod_order = main_ep.ProductionOrder if main_ep else exec_plan.ProductionOrder
                else:
                    prod_order = exec_plan.ProductionOrder

                ws.append([
                    "122",
                    exec_plan.Machine,
                    prod_order.id,
                    exec_plan.ItemRelated.Name,
                    exec_plan.Quantity,
                    exec_plan.ItemRelated.Unit,
                    exec_plan.ST,
                    exec_plan.CoT,
                    prod_order.DD
                ])
        else:
            for exec_plan in ExecutionPlan.new_instances:
                ws.append([
                    "125",
                    exec_plan.Machine,
                    exec_plan.ProductionOrder.id,
                    exec_plan.ItemRelated.Name,
                    exec_plan.Quantity,
                    exec_plan.ItemRelated.Unit,
                    exec_plan.ST,
                    exec_plan.CoT,
                    exec_plan.ProductionOrder.DD
                ])

        wb.save("OUTPUT_MetalPlanDetailed.xlsx")

    def writeDBData(self):
        # Determine connection string based on PT_Settings
        with pyodbc.connect(self.ConnectionString) as conn:
            with conn.cursor() as cursor:
                # Insert TimeUnit instances
                insert_timeunit_query = """INSERT INTO TimeUnits (Machine, StartTime, CompletionTime) VALUES (?, ?, ?)"""
                for TU in TimeUnit.new_instances:
                    cursor.execute(insert_timeunit_query, (TU.Machine, TU.ST, TU.CoT))

                # Insert ExecutionPlan instances
                insert_executionplan_query = """
                INSERT INTO ExecutionPlans (MainItem, Item, Quantity, Machine, ProductionOrder, Position, StartTime, CompletionTime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""

                for exec_plan in ExecutionPlan.new_instances:
                    main_item = exec_plan.ItemRoot.Name if exec_plan.ItemRoot else ''
                    time_unit_position = exec_plan.Position if exec_plan.Position else ''
                    cursor.execute(insert_executionplan_query, (
                        main_item, exec_plan.ItemRelated.Name, exec_plan.Quantity, exec_plan.Machine,
                        exec_plan.ProductionOrder.id, time_unit_position, exec_plan.ST, exec_plan.CoT
                    ))

                # Insert TimeUnitExecutionPlan instances
                insert_timeunit_execplan_query = """
                INSERT INTO TimeUnitExecutionPlans (TimeUnitId, ExecutionPlanId) VALUES (
                    (SELECT id FROM TimeUnits WHERE Machine = ? AND StartTime = ? AND CompletionTime = ?),
                    (SELECT id FROM ExecutionPlans WHERE MainItem = ? AND Item = ? AND Quantity = ? AND Machine = ? 
                    AND ProductionOrder = ? AND Position = ? AND StartTime = ? AND CompletionTime = ?)
                )"""
                
                for TU in TimeUnit.new_instances:
                    for exec_plan in TU.ExecutionPlans:
                        main_item = exec_plan.ItemRoot.Name if exec_plan.ItemRoot else ''
                        time_unit_position = exec_plan.Position if exec_plan.Position else ''
                        cursor.execute(insert_timeunit_execplan_query, (
                            TU.Machine, TU.ST, TU.CoT,
                            main_item, exec_plan.ItemRelated.Name, exec_plan.Quantity, exec_plan.Machine,
                            exec_plan.ProductionOrder.id, time_unit_position, exec_plan.ST, exec_plan.CoT
                        ))

    @staticmethod
    def getSpecificData():
        RODMachines, trefMachines, torcMachines, RODItems, trefItems, torcItems = [], [], [], [], [], []

        for mach in Machines.instances:
            if "ROD0" in mach.MachineCode:
                RODMachines.append(mach)
            elif "MDW0" in mach.MachineCode:
                trefMachines.append(mach)
            elif "BMC" in mach.MachineCode or "BUN0" in mach.MachineCode:
                torcMachines.append(mach)

        for item in Items.instances:
            if item.Process == "ROD":
                RODItems.append(item)
            elif item.Process == "MDW":
                trefItems.append(item)
            elif item.Process == "BUN":
                torcItems.append(item)

        return RODMachines, torcMachines, trefMachines, RODItems, torcItems, trefItems