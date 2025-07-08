import pyomo.environ as po
import numpy as np

import constraint
import helpers

class FCR:
    instantiate_counter = 0

    def __init__(
            self,
            model: po.Model,
            params: dict,
            capacity_price_file: str,
            pos_freq_dev: np.ndarray,
            neg_freq_dev: np.ndarray,
            pos_freq_dev_max: np.ndarray,
            neg_freq_dev_max: np.ndarray
    ):
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.capacity_price_file = capacity_price_file  # File name of the capacity revenue price profile in the directory
        self.pos_freq_dev = pos_freq_dev  # Positive frequency deviations
        self.neg_freq_dev = neg_freq_dev  # Negative frequency deviations
        self.pos_freq_dev_max = pos_freq_dev_max  # 15-min wise maximum of positive frequency deviations
        self.neg_freq_dev_max = neg_freq_dev_max  # 15-min wise maximum of negative frequency deviations
        self.timesteps = self.model.timesteps  # Timesteps of the simulation
        self.duration = 16

        # Counter for naming the blocks uniquely
        FCR.instantiate_counter += 1

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        # General request profile
        self.sum_freq_dev = self.pos_freq_dev + self.neg_freq_dev

        # When frequency above 50 Hz, negative FCR will be provided
        self.source_request = self.sum_freq_dev.copy()
        self.source_request[self.source_request > 0] = 0
        # But still the request profile has to be positive
        self.source_request *= -1

        # When frequency below 50 Hz, positive FCR will be provided
        self.sink_request = self.sum_freq_dev.copy()
        self.sink_request[self.sink_request < 0] = 0

        # Capacity revenue prices
        # Get capacity revenue price profile from a .csv file in the directory
        self.capacity_prices = helpers.get_prices(filename=self.capacity_price_file, column_name='Data')
        self.capacity_prices = self.capacity_prices.repeat(16)
        self.capacity_prices = self.capacity_prices[:len(self.timesteps)]

        # Probability of volume being accepted
        # Create six probabilities for every 4h slot
        self.probability = self.params['fcr_accept_prob'] / 100
        self.stoch_indices = (np.random.rand(self.params['days'] * 6) < self.probability).astype(int)
        # Repeat the profile to match the 96 interval length
        self.stoch_row = self.stoch_indices.repeat(16)


    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name=f'FCRBlock{FCR.instantiate_counter}', val=self.block)

        # Output power of FCR source element [kW]
        self.block.flow_source = po.Var(
            self.timesteps,
            bounds=(self.params['fcr_min_vol'], self.params['fcr_max_vol']),
            within=po.NonNegativeReals
        )

        # Input power of FCR sink element [kW]
        self.block.flow_sink = po.Var(
            self.timesteps,
            bounds=(self.params['fcr_min_vol'], self.params['fcr_max_vol']),
            within=po.NonNegativeReals
        )

        # Optimizers decision whether to activate FCR
        self.block.activation_choice = po.Var(self.timesteps, within=po.Binary)

        # Copy of the source power request to pyomo data format
        self.block.power_request_source = po.Param(
            self.timesteps,
            initialize=self.source_request / 0.2, # linear activation until 0.2 Hz above 50 Hz
            within=po.NonNegativeReals
        )

        # Copy of the sink power request to pyomo data format
        self.block.power_request_sink = po.Param(
            self.timesteps,
            initialize=self.sink_request / 0.2, # linear activation until 0.2 Hz below 50 Hz
            within=po.NonNegativeReals
        )

        # Copy the peak capacity revenue to pyomo data format
        self.block.possible_capacity_revenue = po.Param(
            self.timesteps,
            initialize=self.capacity_prices,
            within=po.NonNegativeReals
        )

        # Real capacity revenue with respect to optimizers decisions
        self.block.capacity_revenue = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Volume to be bid [kW]
        self.block.volume = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Probability of volume bid acceptance
        self.block.bid_accept = po.Param(self.timesteps, initialize=self.stoch_row, within=po.Binary)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        # Ensure volume bid of FCR can only take discrete levels
        if self.params['fcr_levels']:
            constraint.DiscreteLevels(
                model=self.model,
                params=self.params,
                flow=self.block.volume,
                levels=list(range(
                    self.params['fcr_min_vol'], self.params['fcr_max_vol'] + 1, self.params['fcr_step_size'])))

        def reach1_rule(block: po.Block, t: int):
            """Ensure the provision of control reserve in equally distant 4h slots"""
            if t > 0 and t % self.duration != 0:
                return block.volume[t] == block.volume[t - 1]
            else:
                return po.Constraint.Skip

        self.block.reach1_constraint = po.Constraint(self.timesteps, rule=reach1_rule)

        def reach2_rule(block: po.Block, t: int):
            """Ensure the provision of control reserve in equally distant 4h slots"""
            if t > 0 and t % self.duration != 0:
                return block.activation_choice[t] == block.activation_choice[t - 1]
            else:
                return po.Constraint.Skip

        self.block.reach2_constraint = po.Constraint(self.timesteps, rule=reach2_rule)

        def multiplication_source_rule(block: po.Block, t: po.Set):
            """Set the flow to match the source power request when optimizer thinks FCR is needed"""
            return block.flow_source[t] == block.power_request_source[t] * block.activation_choice[t] * block.volume[t] * block.bid_accept[t]

        self.block.multiplication_source_constraint = po.Constraint(self.timesteps, rule=multiplication_source_rule)

        def multiplication_sink_rule(block: po.Block, t: po.Set):
            """Set the flow to match the sink power request when optimizer thinks FCR is needed"""
            return block.flow_sink[t] == block.power_request_sink[t] * block.activation_choice[t] * block.volume[t] * block.bid_accept[t]

        self.block.multiplication_sink_constraint = po.Constraint(self.timesteps, rule=multiplication_sink_rule)

        def capacity_revenue_rule(block: po.Block, t: po.Set):
            """Compute the real capacity revenue with respect to the optimizers decisions"""
            return block.capacity_revenue[t] == block.activation_choice[t] * block.possible_capacity_revenue[t] * block.volume[t] * block.bid_accept[t]

        self.block.capacity_revenue_constraint = po.Constraint(self.timesteps, rule=capacity_revenue_rule)

    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""
        print(f"\n{f'{name} Capacity Price:':<{self.params['val_pos']}} {self.capacity_prices[t]:.2f} ct/kW")
        print(f"{f'{name} Flow:':<{self.params['val_pos']}} {self.block.flow_source[t].value - self.block.flow_sink[t].value:.2f} kW")
        print(f"{f'{name} Activation Choice:':<{self.params['val_pos']}} {self.block.activation_choice[t].value:.0f}")
        print(f"{f'{name} 4h-Bid-accept profile (probabilistic):':<{self.params['val_pos']}} {self.stoch_indices}")
        print(f"{f'{name} Current Bid accepted (probabilistic):':<{self.params['val_pos']}} {self.block.bid_accept[t]:.0f}")
        print(f"{f'{name} 15-min average Frequency Deviation:':<{self.params['val_pos']}} {self.sum_freq_dev[t]:.4f} Hz")
        print(f"{f'{name} absolute Power Request:':<{self.params['val_pos']}} {(self.block.power_request_source[t] - self.block.power_request_sink[t]) * self.params['fcr_max_vol']:.2f} kW")
        print(f"{f'{name} relative Power Request:':<{self.params['val_pos']}} {(self.block.power_request_source[t] - self.block.power_request_sink[t]) * 100:.2f} %")
        print(f"{f'{name} Volume Bid:':<{self.params['val_pos']}} {self.block.volume[t].value:.2f} kW")


class aFRR:
    instantiate_counter = 0

    def __init__(
            self,
            model: po.Model,
            params: dict,
            capacity_price_file: str,
            bid_file: str,
            request_file: str,
            price_file: str,
            freq_profile: np.ndarray,
            freq_extreme: np.ndarray,
            request_profile: np.ndarray
    ):
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.capacity_price_file = capacity_price_file  # File name of the capacity revenue price profile in the directory
        self.bid_file = bid_file # File name of the energy revenue price bids in the directory
        self.request_file = request_file # File name of the request data of aFRR
        self.price_file = price_file # File name of the subsitute aFRR prices instead of market clearing
        self.freq_profile = freq_profile # Frequency deviation profile relevant for aFRR provision
        self.freq_extreme = freq_extreme # Most Extreme frequency deviation in the frequency profile for every 15-min
        self.request_profile = request_profile # System request of aFRR
        self.timesteps = self.model.timesteps  # Timesteps of the simulation
        self.duration = 16

        # Counter for naming the blocks uniquely
        aFRR.instantiate_counter += 1

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        # Probability of the volume bid being accepted
        # Create six probabilities for every 4h slot
        self.probability = self.params['afrr_accept_prob']/100
        self.stoch_indices = (np.random.rand(self.params['days']*6) < self.probability).astype(int)
        # Repeat the profile to match the 96 interval length
        self.stoch_row = self.stoch_indices.repeat(16)

        # Adjust the length to match the simulation duration
        self.request_profile = self.request_profile[:len(self.timesteps)]

        # CAPACITY REVENUE PRICES
        # Get capacity revenue price profile from a .csv file in the directory
        self.capacity_prices = helpers.get_prices(filename=self.capacity_price_file, column_name='Data')
        # Adjust the length to match the simulation duration
        self.capacity_prices = self.capacity_prices.repeat(16)
        self.capacity_prices = self.capacity_prices[:len(self.timesteps)]

        # # Only max in every 4h slot is relevant for capacity revenue price
        # self.poss_revenue = self.capacity_prices * self.request_profile/max(self.request_profile)*self.freq_profile/0.2

        # Binary activation signal of the request
        self.request_profile[self.request_profile>0] = 1
        self.request_profile[self.request_profile<0] = 0

        # ENERGY REVENUE PRICES
        # Get energy revenue price profile from a .csv file in the directory
        if self.params['afrr_market_clearing']:
            self.energy_prices = helpers.market_clearing(request_filename=self.request_file, bid_filename=self.bid_file)
        else:
            self.energy_prices = helpers.get_prices(filename=self.price_file, column_name='Data')
        # Adjust the length to match the simulation duration
        self.energy_prices = self.energy_prices[:len(self.timesteps)]


    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name=f'aFRRBlock{aFRR.instantiate_counter}', val=self.block)

        # Flow of afrr element [kW]
        self.block.flow = po.Var(
            self.timesteps,
            initialize=0,
            bounds=(self.params['afrr_min_vol'], self.params['afrr_max_vol']),
            within=po.NonNegativeReals
        )

        # Optimizers decision whether to activate aFRR
        self.block.activation_choice = po.Var(self.timesteps, within=po.Binary)

        # Copy of the power request to pyomo data format
        self.block.power_request = po.Param(
            self.timesteps,
            initialize=self.request_profile,
            within=po.NonNegativeReals
        )

        # Copy the peak power revenue to pyomo data format
        self.block.possible_capacity_revenue = po.Param(
            self.timesteps,
            initialize=self.capacity_prices,
            within=po.NonNegativeReals
        )

        # Real capacity revenue with respect to optimizers decisions
        self.block.capacity_revenue = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Volume to be bid [kW]
        self.block.volume = po.Var(self.timesteps, within=po.NonNegativeReals)

        # Probability of volume bid acceptance
        self.block.bid_accept = po.Param(self.timesteps, initialize=self.stoch_row, within=po.Binary)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        # Ensure volume bid of aFRR can only take discrete levels
        if self.params['afrr_levels']:
            constraint.DiscreteLevels(
                model=self.model,
                params=self.params,
                flow=self.block.volume,
                levels=list(range(
                    self.params['afrr_min_vol'], self.params['afrr_max_vol'] + 1, self.params['afrr_step_size'])))

        def reach1_rule(block: po.Block, t: int):
            """Ensure the provision of control reserve in equally distant 4h slots"""
            if t > 0 and t % self.duration != 0:
                return block.activation_choice[t] == block.activation_choice[t - 1]
            else:
                return po.Constraint.Skip

        self.block.reach1_constraint = po.Constraint(self.timesteps, rule=reach1_rule)

        def multiplication_rule(block: po.Block, t: po.Set):
            """Set the flow to match the power request when optimizer thinks aFRR is needed"""
            return block.flow[t] == block.power_request[t] * block.activation_choice[t] * block.volume[t] * block.bid_accept[t]

        self.block.multiplication_constraint = po.Constraint(self.timesteps, rule=multiplication_rule)

        def capacity_revenue_rule(block: po.Block, t: po.Set):
            """Compute the real capacity revenue with respect to the optimizers decisions"""
            return block.capacity_revenue[t] == block.activation_choice[t] * block.possible_capacity_revenue[t] * block.volume[t] * block.bid_accept[t]

        self.block.capacity_revenue_constraint = po.Constraint(self.timesteps, rule=capacity_revenue_rule)


    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""
        print(f"\n{f'{name} Capacity Price:':<{self.params['val_pos']}} {self.capacity_prices[t]:.2f} ct/kW")
        print(f"{f'{name} Flow:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")
        print(f"{f'{name} Activation Choice:':<{self.params['val_pos']}} {self.block.activation_choice[t].value:.0f}")
        print(f"{f'{name} 4h-Bid-accept profile (probabilistic):':<{self.params['val_pos']}} {self.stoch_indices}")
        print(f"{f'{name} Current Bid accepted (probabilistic):':<{self.params['val_pos']}} {self.block.bid_accept[t]:.0f}")
        print(f"{f'{name} absolute Power Request:':<{self.params['val_pos']}} {self.block.power_request[t]:.0f}")
        print(f"{f'{name} relative Power Request:':<{self.params['val_pos']}} {self.block.power_request[t]*100:.2f} %")
        print(f"{f'{name} Volume Bid:':<{self.params['val_pos']}} {self.block.volume[t].value:.2f} kW")
        print(f"{f'{name} Capacity Price:':<{self.params['val_pos']}} {self.capacity_prices[t]:.2f} ct/kW")
        print(f"{f'{name} Energy Price:':<{self.params['val_pos']}} {self.energy_prices[t]:.2f} ct/kWh")