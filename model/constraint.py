import pyomo.environ as po


class DiscreteLevels:
    instantiate_counter = 0

    def __init__(self, model: po.ConcreteModel, params: dict, flow: po.Var, levels: list[float]) -> None:
        self.model = model # Model of the simulation
        self.params = params # Parameters of the simulation
        self.flow = flow # Flow to assign the discrete levels to
        self.levels = levels # Discrete levels to be assigned to the flow in [kW]
        self.timesteps = self.model.timesteps  # Timesteps of the simulation

        # Counter for naming the blocks uniquely
        DiscreteLevels.instantiate_counter += 1

        self._init_variables()
        self._add_constraints()

    def _init_variables(self):
        """Initialize all relevant variables"""

        # Block to store all variables
        self.block = po.Block()
        self.model.add_component(name=f'DiscreteLevelsBlock{DiscreteLevels.instantiate_counter}', val=self.block)

        # Set of level indices within the block
        self.block.indices = po.Set(initialize=range(len(self.levels)))

        # Binary decision variable for each element of levels in each timestep
        self.block.decision = po.Var(self.block.indices, self.timesteps, domain=po.Binary)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def upper_bound_rule(block: po.Block, t: int):
            """Flow must equal one of the discrete levels, based on decision variable"""
            return self.flow[t] <= sum(
                (self.levels[i] + self.params['discrete_level_tol']) * block.decision[i, t] for i in block.indices)

        self.block.upper_bound_constraint = po.Constraint(self.timesteps, rule=upper_bound_rule)

        def lower_bound_rule(block: po.Block, t: int):
            """Flow must equal one of the discrete levels, based on decision variable"""
            return self.flow[t] >= sum((self.levels[i] - self.params['discrete_level_tol']) * block.decision[i, t] for i in block.indices)

        self.block.lower_bound_constraint = po.Constraint(self.timesteps, rule=lower_bound_rule)

        def single_choice_rule(block: po.Block, t: int):
            """Only one discrete level can be selected at each timestep"""
            return sum(block.decision[i, t] for i in block.indices) == 1

        self.block.single_choice_constraint = po.Constraint(self.timesteps, rule=single_choice_rule)


class ForceDuration:
    instantiate_counter = 0

    def __init__(self, model: po.ConcreteModel, params: dict, flow: po.Var, duration: int) -> None:
        self.model = model  # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.flow = flow  # Flow to assign the discrete levels to
        self.duration = duration # Amount of 15-min timestamps with steady flow
        self.timesteps = self.model.timesteps  # Timesteps of the simulation

        # Counter for naming the blocks uniquely
        ForceDuration.instantiate_counter += 1

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
        self.model.add_component(name=f'ForceDurationBlock{ForceDuration.instantiate_counter}', val=self.block)


    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def reach_rule(block: po.Block, t: int):
            """Ensure the flow is constant while duration limits are not reached"""
            if t > 0 and t % self.duration != 0:
                return self.flow[t] == self.flow[t - 1]
            else:
                return po.Constraint.Skip

        self.block.reach_constraint = po.Constraint(self.timesteps, rule=reach_rule)


class MutualExclusivity:
    instantiate_counter = 0

    def __init__(self, model: po.Model, params: dict, flow_one: po.Var, flow_two: po.Var) -> None:
        """In a pair of two flows, only one can be bigger than zero at the same timesteps"""
        self.model = model # Model of the simulation
        self.params = params  # Parameters of the simulation
        self.flow_one = flow_one # Flow of the first partner
        self.flow_two = flow_two  # Flow of the second partner
        self.timesteps = self.model.timesteps  # Timesteps of the simulation

        # big-M-tuning parameter
        self.big_M = self.params['batt_power'] * 100

        # Counter for naming the blocks uniquely
        MutualExclusivity.instantiate_counter += 1

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
        self.model.add_component(name=f'MutualExclusivityBlock{MutualExclusivity.instantiate_counter}', val=self.block)

        # Define a binary variable with a unique name, import for when adding multiple constraints of this type
        self.block.mutual = po.Var(self.timesteps, domain=po.Binary)

    def _add_constraints(self):
        """Add constraints to define the custom behavior"""

        def mutual_rule_one(block: po.Block, t: po.Set):
            """Flow one is smaller than a threshold activated by the binary variable mutual"""
            return self.flow_one[t] <= self.big_M * block.mutual[t]

        self.block.mutual_constraint_one = po.Constraint(self.timesteps, rule=mutual_rule_one)

        def mutual_rule_two(block: po.Block, t: po.Set):
            """Flow two is smaller than a threshold and can not be activated while flow one is"""
            return self.flow_two[t] <= self.big_M * (1 - block.mutual[t])

        self.block.mutual_constraint_two = po.Constraint(self.timesteps, rule=mutual_rule_two)


