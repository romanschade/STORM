import pyomo.environ as po
import numpy as np

import helpers

class Spot:
    instantiate_counter = 0

    def __init__(self, model: po.Model, params: dict, price_file: str):
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.timesteps = self.model.timesteps  # Timesteps of the simulation
        self.price_file = price_file  # File name of the price profile in the directory

        # Counter for naming the blocks uniquely
        Spot.instantiate_counter += 1

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        # Get the price profile from a .csv file in the directory
        self.prices = helpers.get_prices(
            filename=self.price_file,
            column_name='Data'
        )

        # Adjust the data to match the simulation duration
        self.prices = self.prices[:len(self.timesteps)]

    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name=f'SPOTBlock{Spot.instantiate_counter}', val=self.block)

        # Input/output power of the spot market element [kW]
        self.block.flow = po.Var(
            self.timesteps,
            initialize=0,
            bounds=(self.params['spot_min_vol'], self.params['spot_max_vol']),
            within=po.NonNegativeReals,
        )


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        # Keep the model from being unbounded in the first iteration step
        self.block.initial_zero_constraint = po.Constraint(
            expr=self.block.flow[0] == 0
        )


    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""

        print(f"\n{f'{name}-price:':<{self.params['val_pos']}} {self.prices[t]:.2f} ct/kWh")
        print(f"{f'Flow of {name}:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")
        print(f"{f'Flow of {name}:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")