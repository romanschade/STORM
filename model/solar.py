import pyomo.environ as po
import numpy as np

class PV_System():
    def __init__(self, model: po.Model, params: dict):
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.timesteps = self.model.timesteps  # Timesteps of the simulation

        self._get_inputs()
        self._init_variables()
        self._add_constraints()


    def _get_inputs(self):
        """Get all relevant inputs"""

        # Create a variable with the correct length
        amount_steps = len(self.timesteps)/self.params['days']
        time_steps = np.arange(amount_steps)  # 96 periods for 15-min day simulation

        # Mathematics of the profile
        mean_position = (amount_steps - 1) / 2  # peak at 12 PM
        self.profile = np.exp(-0.5 * ((time_steps - mean_position) / self.params['pv_std_dev']) ** 2)
        self.profile = np.tile(self.profile, self.params['days'])


    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name='pv_block', val=self.block)

        # Power output of the PV system [kW]
        self.block.flow = po.Var(
            self.timesteps,
            initialize=0,
            within=po.NonNegativeReals
        )

        # Nominal power of the PV system [kW]
        self.block.power = po.Param(
            self.timesteps,
            initialize=self.profile * self.params['pv_power'],
            within=po.NonNegativeReals
        )

        # Binary decision whether to provide PV Power
        self.block.decision = po.Var(
            self.timesteps,
            within=po.Binary
        )


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def activation_rule(block: po.Block, t: int):
            """Decide on whether to activate PV Power"""
            return block.flow[t] == block.power[t] * block.decision[t]

        self.block.activation_constraint = po.Constraint(self.timesteps, rule=activation_rule)


    def get_results(self, t: int, name: str) -> None:
        """Print out all variables to the terminal"""

        print(f"\n{f'Flow from {name}:':<{self.params['val_pos']}} {self.block.flow[t].value:.2f} kW")
        print(f"{f'Possible Flow from {name}:':<{self.params['val_pos']}} {self.block.power[t]:.2f} kW")
        print(f"{f'{name} Activation choice:':<{self.params['val_pos']}} {self.block.decision[t].value:.0f}")

