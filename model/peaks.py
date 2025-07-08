import pyomo.environ as po

import constraint

class PeakShaving:
    def __init__(self, model: po.Model, flow_list: list[po.Var], params: dict) -> None:
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.timesteps = self.model.timesteps  # Timesteps of the simulation
        self.flow_list = flow_list  # Component from which the flow comes

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        pass


    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name=f'PeakShavingBlock', val=self.block)

        # Supply power from electricity grid in every time step
        self.block.supply_power = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Total supply power from electricity grid
        self.block.total_supply_power = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Variable for storing the peak power over all timestamps
        self.block.p_max = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Special behavior when taking considering full-load hours/time
        if self.params['full_load_time']:
            # Capacity price of electricity supply from grid
            self.block.cap_price = po.Var(self.timesteps, within=po.NonNegativeReals)

            # Energy price of electricity supply from grid
            self.block.en_price = po.Var(self.timesteps, within=po.NonNegativeReals)

            # Full load time
            self.block.full_load_time = po.Var(self.timesteps, within=po.NonNegativeReals)

            # Total Full load time
            self.block.total_full_load_time = po.Var(self.timesteps, within=po.NonNegativeReals)

            # Capacity price component of net grid supply costs [€]
            self.block.cost = po.Var(self.timesteps, within=po.NonNegativeReals)

            # big-M-tuning parameter
            self.big_M = self.params['days'] * self.params['batt_power'] * 100

            # Indication on whether the total full load time is above the limit or not
            self.block.delta = po.Var(self.timesteps, within=po.Binary)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def compute_supply_rule(block: po.Block, t: int):
            """Compute the supply from electricity grid for every timestep"""
            return block.supply_power[t] == sum(flow[t] for flow in self.flow_list)

        self.block.compute_supply_constraint = po.Constraint(self.timesteps, rule=compute_supply_rule)

        def total_supply_rule(block: po.Block, t: int):
            """Compute the total supply from electricity grid over all timesteps"""
            if t > 0:
                return block.total_supply_power[t] == block.total_supply_power[t - 1] + block.supply_power[t]
            return block.total_supply_power[t] == 0

        self.block.total_supply_constraint = po.Constraint(self.timesteps, rule=total_supply_rule)

        def copy_value_rule(block: po.Block, t: int):
            """Copy the gird source flow values"""
            return block.p_max[t] >= block.supply_power[t]

        self.block.copy_value_constraint = po.Constraint(self.timesteps, rule=copy_value_rule)

        def peak_value_rule(block: po.Block, t: int):
            """Ensure peak value is non-decreasing over timesteps"""
            if t > 0:
                return block.p_max[t] >= block.p_max[t - 1]
            return po.Constraint.Skip

        self.block.peak_value_constraint = po.Constraint(self.timesteps, rule=peak_value_rule)

        if self.params['full_load_time']:
            # Ensure the capacity price applies to all timesteps
            constraint.ForceDuration(
                model=self.model,
                params=self.params,
                flow=self.block.cap_price,
                duration=len(self.timesteps)
            )

            # Ensure the energy price applies to all timesteps
            constraint.ForceDuration(
                model=self.model,
                params=self.params,
                flow=self.block.en_price,
                duration=len(self.timesteps)
            )

            def first_big_m_rule(block: po.Block, t: int):
                """Check if full-load time is above the limit (part 1)"""
                return block.total_supply_power[t] - (self.params['full_load_limit'] / 100 * len(self.timesteps)) * block.p_max[t] >= - self.big_M * (1 - block.delta[t])

            self.block.first_big_m_constraint = po.Constraint(self.timesteps, rule=first_big_m_rule)

            def second_big_m_rule(block: po.Block, t: int):
                """Check if full-load time is above the limit (part 2)"""
                return block.total_supply_power[t] - (self.params['full_load_limit'] / 100 * len(self.timesteps)) * block.p_max[t] <= 0.001 + self.big_M * block.delta[t]

            self.block.second_big_m_constraint = po.Constraint(self.timesteps, rule=second_big_m_rule)

            def compute_cost_rule(block: po.Block, t: int):
                """Compute the power component of net grid supply costs [€]"""
                return block.cost[t] == block.p_max[t] * block.cap_price[t]

            self.block.compute_cost_constraint = po.Constraint(self.timesteps, rule=compute_cost_rule)

            def switch_capacity_price_rule(block: po.Block, t: int):
                """Switch between the two capacity prices"""
                return block.cap_price[t] == self.params['net_capacity_price_above'] * block.delta[len(self.timesteps) - 1] + self.params['net_capacity_price_below'] * (1 - block.delta[len(self.timesteps) - 1])

            self.block.switch_capacity_price_constraint = po.Constraint(self.timesteps, rule=switch_capacity_price_rule)

            def switch_energy_price_rule(block: po.Block, t: int):
                """Switch between the two energy prices"""
                return block.en_price[t] == self.params['net_energy_price_above'] * block.delta[len(self.timesteps) - 1] + self.params['net_energy_price_below'] * (1 - block.delta[len(self.timesteps) - 1])

            self.block.switch_energy_price_constraint = po.Constraint(self.timesteps, rule=switch_energy_price_rule)


    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""
        print(f"\n{f'Current Energy Supply from Grid:':<{self.params['val_pos']}} {po.value(self.block.supply_power[t]) * 0.25:.2f} kWh")
        print(f"{f'Total Energy Supply from Grid until now:':<{self.params['val_pos']}} {po.value(self.block.total_supply_power[t]) * 0.25:.2f} kWh")
        print(f"{f'Maximum Power from Grid until now:':<{self.params['val_pos']}} {po.value(self.block.p_max[t]):.2f} kW")
        if self.params['full_load_time']:
            print(f"{f'Net Capacity Price:':<{self.params['val_pos']}} {po.value(self.block.cap_price[t]):.3f} €/kW")
            print(f"{f'Net Energy Price:':<{self.params['val_pos']}} {po.value(self.block.en_price[t]) * 100:.3f} ct/kWh")
