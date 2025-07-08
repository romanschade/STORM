import pyomo.environ as po

class Battery:
    def __init__(self, model: po.Model, params: dict):
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.timesteps = self.model.timesteps  # Timesteps of the simulation

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        pass


    def _init_variables(self):
        """Initialize all relevant variables"""

        # Create a block to store the variables
        self.block = po.Block()
        self.model.add_component(name='batt_block', val=self.block)

        # Battery input/output power [kW]
        self.block.flow = po.Var(
            self.timesteps,
            initialize=0,
            bounds=(-self.params['batt_power'], self.params['batt_power']),
            within=po.Reals
        )

        # Absolute value of battery input/output power [kW]
        self.block.flow_abs = po.Var(self.timesteps, initialize=0, within=po.NonNegativeReals)

        # Battery state of charge [kWh]
        self.block.soc = po.Var(
            self.timesteps,
            initialize=self.params['batt_capacity']*0.5, # Initial SoC
            bounds=(self.params['batt_min_soc']*self.params['batt_capacity'], # Minimum SoC limit
                    self.params['batt_max_soc']*self.params['batt_capacity']), # Maximum SoC limit
            within = po.NonNegativeReals
        )

        # Total discharged energy for mobility [kWh]
        self.block.discharged = po.Var(self.timesteps, initialize=0, within=po.Reals)

        # Relevant for mobility behavior
        if self.params['add_mobility']:
            # Battery charging/discharging power [kW]
            self.block.charging = po.Var(self.timesteps, initialize=0, within=po.Reals)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def abs_flow_upper_pos_rule(block: po.Block, t: int):
            """Positive flow contribute to the absolute value"""
            return block.flow_abs[t] >= block.flow[t]

        self.block.abs_flow_upper_pos_constraint = po.Constraint(self.timesteps, rule=abs_flow_upper_pos_rule)

        def abs_flow_upper_neg_rule(block: po.Block, t: int):
            """Negative flow contribute to the absolute value"""
            return block.flow_abs[t] >= -block.flow[t]

        self.block.abs_flow_upper_neg_constraint = po.Constraint(self.timesteps, rule=abs_flow_upper_neg_rule)


        if self.params['batt_balanced']:

            def battery_balanced_rule(block: po.Block, t: int):
                """The SoC at the beginning of the simulation match the one at the end of the simulation"""
                return block.soc[0] == block.soc[len(self.timesteps) - 1]

            self.block.battery_balanced_constraint = po.Constraint(expr=battery_balanced_rule)


        if self.params['add_mobility']:

            def is_weekday(t):
                """Returns True if time step t is in a weekday (Mon–Fri)"""
                steps_per_day = 96
                day = t // steps_per_day
                return day < 5  # Monday (0) to Friday (4)

            def departure_rule(block: po.Block, t: int):
                """Set the SoC at the time of departure to meet the users input"""
                if is_weekday(t) and (t % 96) == self.params['dep_step']:
                    return block.soc[t] == (self.params['batt_min_soc'] + self.params['dep_user_soc'] / 100 * (self.params['batt_max_soc'] - self.params['batt_min_soc'])) * self.params['batt_capacity']
                return po.Constraint.Skip

            self.block.departure_constraint = po.Constraint(self.timesteps, rule=departure_rule)

            def arrival_rule(block: po.Block, t: int):
                """Set the SoC at the time of arrival to meet the users input"""
                if is_weekday(t) and (t % 96) == (self.params['arr_step'] - 1):
                    return block.soc[t] == (self.params['batt_min_soc'] + self.params['arr_user_soc'] / 100 * (self.params['batt_max_soc'] - self.params['batt_min_soc'])) * self.params['batt_capacity']
                return po.Constraint.Skip

            self.block.arrival_constraint = po.Constraint(self.timesteps, rule=arrival_rule)

            def discharging_weekday_rule(block: po.Block, t: int):
                """Virtual discharging is happening one step before arrival of the vehicle on weekdays"""
                if is_weekday(t) and (t % 96) != (self.params['arr_step'] - 1):
                    return block.charging[t] == 0
                return po.Constraint.Skip

            self.block.discharging_weekday_constraint = po.Constraint(self.timesteps, rule=discharging_weekday_rule)

            def discharging_weekend_rule(block: po.Block, t: int):
                """Virtual discharging is prohibited on weekends"""
                if not is_weekday(t):
                    return block.charging[t] == 0
                return po.Constraint.Skip

            self.block.discharging_weekend_constraint = po.Constraint(self.timesteps, rule=discharging_weekend_rule)

            def total_discharged_rule(block: po.Block, t: int):
                """Compute the total discharged energy for mobility over all timesteps"""
                if t > 0:
                    return block.discharged[t] == block.discharged[t - 1] + block.charging[t]
                return block.discharged[t] == 0

            self.block.total_discharged_constraint = po.Constraint(self.timesteps, rule=total_discharged_rule)

            def meantime_flow_rule(block: po.Block, t: int):
                """The battery is offline in between the time of departure and arrival"""
                if is_weekday(t):
                    time_of_day = t % 96
                    if time_of_day in range(self.params['dep_step'] + 1, self.params['arr_step']):
                        return block.flow[t] == 0
                return po.Constraint.Skip

            self.block.meantime_flow_constraint = po.Constraint(self.timesteps, rule=meantime_flow_rule)

            def battery_balance_rule(block: po.Block, t: int):
                """The SoC of the battery will only change upon power input or output"""
                if t == 0:
                    return block.soc[t] == self.params['batt_initial_soc'] * self.params['batt_capacity']
                return block.soc[t] == block.soc[t - 1] + 0.25 * self.params['batt_efficiency'] * (block.flow[t] + block.charging[t])

            self.block.battery_balance_constraint = po.Constraint(self.timesteps, rule=battery_balance_rule)


        else: # Virtual discharging must not be allowed without mobility

            def battery_balance_rule(block: po.Block, t: int):
                """The SoC of the battery will only change upon power input or output"""
                if t == 0:
                    return block.soc[t] == self.params['batt_initial_soc'] * self.params['batt_capacity']
                return block.soc[t] == block.soc[t - 1] + 0.25 * self.params['batt_efficiency'] * block.flow[t]

            self.block.battery_balance_constraint = po.Constraint(self.timesteps, rule=battery_balance_rule)


    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""

        print(f"\n{f'Flow to the {name}:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")
        print(f"{f'Absolute Value of Flow to the {name}:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")
        print(f"{f'Total Energy for Mobility:':<{self.params['val_pos']}} {-self.block.discharged[t].value * 0.25:.2f} kWh")
        print(f"{f'Absolute {name} SoC:':<{self.params['val_pos']}} {self.block.soc[t].value:.2f} kWh")
        print(f"{f'Relative {name} SoC:':<{self.params['val_pos']}} {self.block.soc[t].value / self.params['batt_capacity'] * 100:.2f} %")




