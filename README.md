# STORM
Storage Optimization in regulated Markets

STORM is an open-source, MILP model designed to optimize the economics of storage systems participating in multiple markets such as day-ahead, intraday auction, FCR and aFRR. 
Particular focus is on modeling the regulatory within the Germany as well as legislation, which includes minimum bid sizes at spot and balancing markets, separate capacity and energy auctions in aFRR, market clearing principles like pay-as-cleared and pay-as-bid, prohibition of malicious market strategies, network fees price changes with increasing full-load hours, and more. 
In addition, there is an option to allow mobility behavior of the battery storage so the battery is assumed to be an electric vehicle. 
The optimization is primarily built upon Pyomo supported by NumPy and Pandas.

The overall design is a script-based code with modular object-oriented structure. This means that there is an almost linear sequence of code within the main.py, supported by classes and functions in other files containing more complex parts of the model. 

![image](https://github.com/user-attachments/assets/597cfcab-4aa8-40cd-a2d0-74ed10e456cf)

The components available are a battery, a PV system, day-ahead and intraday auction markets, FCR, aFRR+, and aFRR-. All of these are coupled both phyisically via their power flows as well as economically via revenues/costs. The optimization goal is maximazation of profit.

![image](https://github.com/user-attachments/assets/80c8f61f-bef5-4397-9e3e-25da83e77859)

The model can be controlled using the settings.xlsx file in the input directory. The following denotes some of the parameters:

Simulation Parameters
- add_pv adds a PV system with guassian-shaped profile and deactivation option to the model.
- add_battery adds a (battery) storage system with optional mobility behavior to the model.
- add_mobility activates the mobility behavior of the battery always in the first five days of a week of the simulation duration (Mo. - Fr.)
- add_id_buy adds an intraday market with 15-min resolution to the model where energy can be bought.
- add_id_sell adds an intraday market with 15-min resolution to the model where energy can be sold.
- add_da_buy adds a day-ahead market with 60-min resolution to the model where energy can be bought.
- add_da_sell adds a day-ahead market with 60-min resolution to the model where energy can be sold.
- add_fcr adds a FCR market to the model which gives energy to the model or takes energy from it depending on the grid frequency deviation.
- add_afrrp adds an aFRR+ market to the model which takes energy from the energy system depending on the grid frequency deviation and theh overall aFRR+ request.
- add_afrrn adds an aFRR- market to the model whcih htakes energy from the energy system depending on the grid frequency deviation and the overall aFRR- request.
- add_ps adds the use case peak shaving to the model, either with fixed price or variable price tuple depending on the value of the parameter 'full_load_time'.
- discrete_level_tol specifies the tolerance of meeting the discrete level constraint for associated variables.
- no_counter_trade prohibits trading at opposing markets like FCR+ and aFRR- at the same time.
- solver specifies the solver to be used (gurobi, cbc, ...).
- days specifies the duration of the simulation. Every day has 96 timesteps of 15 minutes each. A miximum duration of 7 days is recommended.
- plot_inputs activates the option to plot the input data graphically as .html.
- plot_outputs activates the option to plot the output data graphically as .html.
- see_meta allows to see the meta data of the optimization during the optimization run in the console.
- print_meta prints a fraction of the meta data to the console after execution of the optimization.
- print_results prints the results of the optimization to the console including power flows, price data and activation choices of the optimizer.

Spot Market Parameters
- spot_min_vol specifies the minimum power volume of any of the spot market elements.
- spot_max_vol specifies the maximum power volume of any of the spot market elements.
- spot_levels constraints the spot power flows to take only discrete levels (0, 100, 200, ... kW for exammple).
- spot_step_size specifies the step size between maximum and minimum power volume when constraining the power flows to discrete levels.

Balancing Paramters
- afrr_min_vol specifies the minimum power volume of any of the aFRR market elements.
- afrr_max_vol specifies the maximum power volume of any of the aFRR market elements.
- afrr_levels constraints the aFRR power flows to take only discrete levels.
- afrr_step_size specifies the step size between maximum and minimum power volume when constraining the power flows to discrete values.
- afrr_accept_prob specifies the probability of aFRR volume bids being accepted.
- afrr_market_clearing activates the merit-order market clearing mechanism for both aFRR markets based on the bids and the historical activation.
- fcr_min_vol specifies the minimum power volume of the FCR market element.
- fcr_max_vol specifies the maximum power volume of the FCR market element.
- fcr_levels constraint the FCR power flows to take only discrete levels.
- fcr_step_size specifies the step size between maximum and minimum power volume when constraining the power flows to discrete values.
- fcr_accept_prob specifies the probability of FCR volume bibds being accepted.

PV Parameters
- pv_power specifies the peak power of the PV system.
- pv_std_dev specifies the standard deviation of the guassian-shaped PV curve.
- pv_cost specifies the cost of PV generation and deliver to the energy system.

Network Parameters
- net_energy_price specifies the energy price of network fees when no peak shaving or peak shaving with fixed price is activated.
- net_capacity_price specifies the capacity price of network fees when peak shaving with fixed price is activated.
- full_load_time activated the variant of peak shaving with variable prices (tuple of energy and capacity price).
- full_load_limit specifies the limit for the change of the price tuple in peak shaving with variable prices.
- net_capacity_price_below specifies the network fees' capacity price in peak shaving with variable prices below the full-load-time.
- net_energy_price_below specifies the network fees' energy price in peak shaving with variable prices below the full-load-time.
- net_capacity_price_above specifies the network fees' capacity price in peak shaving with variable prices above the full-load-time.
- net_energy_price_above specifies the network fees' energy price in peak shaving with variable prices above the full-load-time.

Battery Parameters
- batt_capacity specifies the nominal capacity of the (battery) storage system.
- batt_power specifies the nominal power of the (battery) storage system.
- batt_min_soc specifies the minimum SoC of the (battery) storage system.
- batt_max_soc specifies the maximum SoC of the (battery) storage system.
- batt_initial_soc specifies the intial SoC at  t=0 of the (battery) storage system.
- batt_efficiency specifies the inflow and outflow efficiency of the energy flows of the (battery) storage system.
- batt_balanced constraint the initial SoC (t=0) to be equal to the final SoC (t=T).
- batt_op_cost specifiefs the cost of operation of the battery per charged or discharged kWh.
- dep_user_soc constraints the SoC at departure of mobility to take a certain value.
- dep_step specifies the timestep of departure for mobility.
- arr_user_soc constraints the SoC at arrival of mobility to take a certain value.
- arr_step specifies the timestep of arrival for mobility.  
