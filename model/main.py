import pyomo.environ as po
import pandas as pd
import numpy as np
import time
import os

import helpers
import visualizer
import battery
import solar
import spot
import constraint
import balancing
import peaks

def main():
    """STORM - Storage Optimization in regulated markets"""
    # Set the timer for the program execution time
    start_time = time.time()

    # Import parameters and settings from an Excel file in the directory
    params_path = os.path.join(os.path.dirname(__file__), '../Inputs/settings.xlsx')
    params = helpers.get_params(path=params_path, scenario='Ref_Sens')

    # Set the duration of the simulation
    intervals = 96 * params['days']
    indices = list(range(intervals))

    # Prepare to plot input data
    if params['plot_inputs']:
        input_plot = visualizer.Visualizer(
            title='_Plot_Inputs',
            x_label='15-min Time Periods',
            y_label='[-]',
            target_directory="../inputs"
        )
    # Prepare to plot output data
    if params['plot_outputs']:
        output_plot = visualizer.Visualizer(
            title='_Plot_Outputs',
            x_label='15-min Time Periods',
            y_label='[kW or kWh]',
            target_directory="../outputs"
        )

    # Create the Pyomo model
    model = po.ConcreteModel()
    model.timesteps = po.Set(initialize=indices)
    objective_function = 0

    # Net frequency pre-processing
    if params['add_fcr'] or params['add_afrrp'] or params['add_afrrn']:
        avrg_pos_dev, avrg_neg_dev, pos_dev_max, neg_dev_max = helpers.get_frequencies(
            filename='../inputs/NET_FREQUENCY_DAILY.csv',
            column_name='Data')
        # Tile the data to match the simulation duration
        avrg_pos_dev = np.tile(avrg_pos_dev, params['days'])
        pos_dev_max = np.tile(pos_dev_max, params['days'])
        avrg_neg_dev = np.tile(avrg_neg_dev, params['days'])
        neg_dev_max = np.tile(neg_dev_max, params['days'])
    # Link the data to the input plot
    if params['plot_inputs']:
        if params['add_afrrn']:
            input_plot.append_curve_plot(
                data=avrg_pos_dev,
                name='Average of pos. Frequency Deviations [Hz]',
                color='purple',
                style='dash'
            )
            input_plot.append_curve_plot(
                data=pos_dev_max,
                name='Max of pos. Frequency Deviations [Hz]',
                color='purple',
                style='solid'
            )
        if params['add_afrrp']:
            input_plot.append_curve_plot(
                data=avrg_neg_dev,
                name='Average of neg. Frequency Deviations [Hz]',
                color='darkcyan',
                style='dash'
            )
            input_plot.append_curve_plot(
                data=neg_dev_max,
                name='Max of neg. Frequency Deviations [Hz]',
                color='darkcyan',
                style='solid'
            )
        if params['add_fcr']:
            input_plot.append_curve_plot(
                data=avrg_pos_dev + avrg_neg_dev,
                name='Average Frequency Deviations [Hz]',
                color='magenta',
                style='dash'
            )

    # Load aFRRp request profile
    if params['add_afrrp']:
        afrrp_request_path = '../inputs/aFRRp_REQUEST_WEEKLY.csv'
        afrrp_path = os.path.join(os.path.dirname(__file__), afrrp_request_path)
        afrrp_data = pd.read_csv(afrrp_path, sep=",")
        afrrp_request_profile = np.array(afrrp_data['Data'])
    # Load aFRRn request profile
    if params['add_afrrn']:
        afrrn_request_path = '../inputs/aFRRn_REQUEST_WEEKLY.csv'
        afrrn_path = os.path.join(os.path.dirname(__file__), afrrn_request_path)
        afrrn_data = pd.read_csv(afrrn_path, sep=",")
        afrrn_request_profile = np.array(afrrn_data['Data'])

    # Create a battery
    if params['add_battery']:
        batt = battery.Battery(model=model, params=params)
    # Create a PV system
    if params['add_pv']:
        pv = solar.PV_System(model=model, params=params)
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=pv.profile,
                name='PV_Profile [-]',
                color='orange',
                style='solid'
            )
    # Create an intraday source
    if params['add_id_buy']:
        id_buy = spot.Spot(model=model, params=params, price_file='../inputs/ID_PRICES_WEEKLY.csv')
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=id_buy.prices,
                name='ID_Buy_Prices [ct/kWh]',
                color='red',
                style='solid'
            )
    # Create an intraday sink
    if params['add_id_sell']:
        id_sell = spot.Spot(model=model, params=params, price_file='../inputs/ID_PRICES_WEEKLY.csv')
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=id_sell.prices,
                name='ID_Sell_Prices [ct/kWh]',
                color='red',
                style='dash'
            )
    # Create a day-ahead source
    if params['add_da_buy']:
        da_buy = spot.Spot(model=model, params=params, price_file='../inputs/DA_PRICES_WEEKLY.csv')
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=da_buy.prices,
                name='DA_Buy_Prices [ct/kWh]',
                color='green',
                style='solid'
            )
    # Create a day-ahead sink
    if params['add_da_sell']:
        da_sell = spot.Spot(model=model, params=params, price_file='../inputs/DA_PRICES_WEEKLY.csv')
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=da_sell.prices,
                name='DA_Sell_Prices [ct/kWh]',
                color='green',
                style='dash'
            )
    # Create FCR source and sink
    if params['add_fcr']:
        fcr = balancing.FCR(
            model=model,
            params=params,
            capacity_price_file='../inputs/FCR_CAPACITY_PRICES_WEEKLY.csv',
            pos_freq_dev=avrg_pos_dev,
            neg_freq_dev=avrg_neg_dev,
            pos_freq_dev_max=pos_dev_max,
            neg_freq_dev_max=neg_dev_max
        )
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=fcr.capacity_prices,
                name='FCR Capacity Prices [ct/kW]',
                color='grey',
                style='solid'
            )
    # Create aFRRn source
    if params['add_afrrn']:
        afrrn = balancing.aFRR(
            model=model,
            params=params,
            capacity_price_file='../inputs/aFRRn_CAPACITY_PRICES_WEEKLY.csv',
            bid_file='../inputs/aFRRn_ENERGY_BIDS_WEEKLY.csv',
            request_file=afrrn_request_path,
            price_file='../inputs/aFRRn_ENERGY_PRICES_WEEKLY.csv',
            freq_profile=avrg_pos_dev,
            freq_extreme=pos_dev_max,
            request_profile=afrrn_request_profile
        )
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=afrrn.energy_prices,
                name='aFRR- Energy Prices [ct/kWh]',
                color='grey',
                style='dash'
            )
            input_plot.append_curve_plot(
                data=afrrn.capacity_prices,
                name='aFRR- Capacity Prices [ct/kW]',
                color='grey',
                style='solid'
            )
    # Create aFRRp sink
    if params['add_afrrp']:
        afrrp = balancing.aFRR(
            model=model,
            params=params,
            capacity_price_file='../inputs/aFRRp_CAPACITY_PRICES_WEEKLY.csv',
            bid_file='../inputs/aFRRp_ENERGY_BIDS_WEEKLY.csv',
            request_file=afrrp_request_path,
            price_file='../inputs/aFRRp_ENERGY_PRICES_WEEKLY.csv',
            freq_profile=-avrg_neg_dev,
            freq_extreme=-neg_dev_max,
            request_profile=afrrp_request_profile
        )
        if params['plot_inputs']:
            input_plot.append_curve_plot(
                data=afrrp.energy_prices,
                name='aFRR+ Energy Prices [ct/kWh]',
                color='grey',
                style='dash'
            )
            input_plot.append_curve_plot(
                data=afrrp.capacity_prices,
                name='aFRR+ Capacity Prices [ct/kW]',
                color='grey',
                style='solid'
            )

    # Plot the inputs
    if params['plot_inputs']:
        input_plot.generate_curve_plot(show=True)

    # Add custom constraints
    # Forced Duration of Day-Ahead
    if params['add_da_buy']:
        constraint.ForceDuration(
            model=model,
            params=params,
            flow=da_buy.block.flow,
            duration=4
        )
    if params['add_da_sell']:
        constraint.ForceDuration(
            model=model,
            params=params,
            flow=da_sell.block.flow,
            duration=4
        )
    # Discrete levels for spot market trading
    if params['spot_levels']:
        # Discrete levels on intraday buy
        if params['add_id_buy']:
            constraint.DiscreteLevels(
                model=model,
                params=params,
                flow=id_buy.block.flow,
                levels=list(range(params['spot_min_vol'], params['spot_max_vol'] + 1, params['spot_step_size'])))
        # Discrete levels on intraday sell
        if params['add_id_sell']:
            constraint.DiscreteLevels(
                model=model,
                params=params,
                flow=id_sell.block.flow,
                levels=list(range(params['spot_min_vol'], params['spot_max_vol'] + 1, params['spot_step_size'])))
        # Discrete levels on day-ahead buy
        if params['add_da_buy']:
            constraint.DiscreteLevels(
                model=model,
                params=params,
                flow=da_buy.block.flow,
                levels=list(range(params['spot_min_vol'], params['spot_max_vol'] + 1, params['spot_step_size'])))
        # Discrete levels on day-ahead sell
        if params['add_da_sell']:
            constraint.DiscreteLevels(
                model=model,
                params=params,
                flow=da_sell.block.flow,
                levels=list(range(params['spot_min_vol'], params['spot_max_vol'] + 1, params['spot_step_size'])))
    # Prohibition of opposing market trading (i.e. FCR+ and aFRR-)
    if params['no_counter_trade']:
        # No simultaneous trading at ID market
        if params['add_id_buy'] and params['add_id_sell']:
            constraint.MutualExclusivity(
                model=model,
                params=params,
                flow_one=id_buy.block.flow,
                flow_two=id_sell.block.flow
            )
        # No simultaneous trading at DA market
        if params['add_da_buy'] and params['add_da_sell']:
            constraint.MutualExclusivity(
                model=model,
                params=params,
                flow_one=da_buy.block.flow,
                flow_two=da_sell.block.flow
            )
        # No simultaneous trading at SPOT market and FCR at the same time
        if params['add_fcr']:
            # Conflict between ID-buy and FCRp
            if params['add_id_buy']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=id_buy.block.flow,
                    flow_two=fcr.block.flow_sink
                )
            # Conflict between ID-sell and FCRn
            if params['add_id_sell']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=id_sell.block.flow,
                    flow_two=fcr.block.flow_source
                )
            # Conflict between DA-buy and FCRp
            if params['add_da_buy']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=da_buy.block.flow,
                    flow_two=fcr.block.flow_sink
                )
            # Conflict between DA-sell and FCRn
            if params['add_da_sell']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=da_sell.block.flow,
                    flow_two=fcr.block.flow_source
                )
        # No simultaneous trading at SPOT market and aFRRn at the same time
        if params['add_afrrn']:
            # Conflict between ID-sell and aFRRn
            if params['add_id_sell']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=id_sell.block.flow,
                    flow_two=afrrn.block.flow
                )
            # Conflict between DA-sell and aFRRn
            if params['add_da_sell']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=da_sell.block.flow,
                    flow_two=afrrn.block.flow
                )
        # No simultaneous trading at SPOT market and aFRRp at the same time
        if params['add_afrrp']:
            # Conflict between ID-buy and aFRRp
            if params['add_id_buy']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=id_buy.block.flow,
                    flow_two=afrrp.block.flow
                )
            # Conflict between DA-buy and FCRp
            if params['add_da_buy']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=da_buy.block.flow,
                    flow_two=afrrp.block.flow
                )
        # No simultaneous trading at FCR and aFRR at the same time
        if params['add_fcr']:
            # Conflict between FCRp and aFRRn
            if params['add_afrrn']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=fcr.block.flow_sink,
                    flow_two=afrrn.block.flow
                )
            # Conflict between FCRn and aFRRp
            if params['add_afrrp']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=fcr.block.flow_source,
                    flow_two=afrrp.block.flow
                )
        # No simultaneous trading at aFRRn and aFRRp at the same time
        if params['add_afrrn']:
            # Conflict between FCRp and aFRRn
            if params['add_afrrp']:
                constraint.MutualExclusivity(
                    model=model,
                    params=params,
                    flow_one=afrrn.block.flow,
                    flow_two=afrrp.block.flow
                )
    # Peak Shaving
    if params['add_ps']:
        ps_relevant = []
        # Contribution of ID-buy
        if params['add_id_buy']:
            ps_relevant.append(id_buy.block.flow)
        # Contribution of DA-buy
        if params['add_da_buy']:
            ps_relevant.append(da_buy.block.flow)
        # Contribution of FCR-
        if params['add_fcr']:
            ps_relevant.append(fcr.block.flow_source)
        # Contribution of aFRRn
        if params['add_afrrn']:
            ps_relevant.append(afrrn.block.flow)
        # Add Constraint
        ps = peaks.PeakShaving(model=model, params=params, flow_list=ps_relevant)
    # The FCR volume bid can never exceed the sum of battery power and PV power
    if params['add_battery'] and params['add_fcr']:
        def fcr_volume_exceed_rule(model: po.Model, t: int):
            return fcr.block.volume[t] <= (
                params['batt_power'] + pv.block.power[t] if params['add_pv'] else params['batt_power'])

        model.fcr_volume_exceed_constraint = po.Constraint(model.timesteps, rule=fcr_volume_exceed_rule)
    # The aFRRp volume bid can never exceed the sum of battery power and PV power
    if params['add_battery'] and params['add_afrrp']:
        def afrrp_volume_exceed_rule(model: po.Model, t: int):
            return afrrp.block.volume[t] <= (
                params['batt_power'] + pv.block.power[t] if params['add_pv'] else params['batt_power'])

        model.afrrp_volume_exceed_constraint = po.Constraint(model.timesteps, rule=afrrp_volume_exceed_rule)

    # Energy balance
    def power_balance_rule(model: po.Model, t: int):
        """Energy can neither be created nor destroyed within the system"""
        return (0 ==
                - (batt.block.flow[t] if params['add_battery'] else 0)
                + (pv.block.flow[t] if params['add_pv'] else 0)
                + (id_buy.block.flow[t] if params['add_id_buy'] else 0)
                - (id_sell.block.flow[t] if params['add_id_sell'] else 0)
                + (da_buy.block.flow[t] if params['add_da_buy'] else 0)
                - (da_sell.block.flow[t] if params['add_da_sell'] else 0)
                + (fcr.block.flow_source[t] if params['add_fcr'] else 0)
                - (fcr.block.flow_sink[t] if params['add_fcr'] else 0)
                + (afrrn.block.flow[t] if params['add_afrrn'] else 0)
                - (afrrp.block.flow[t] if params['add_afrrp'] else 0)
                )

    model.power_balance_constraint = po.Constraint(model.timesteps, rule=power_balance_rule)

    # Define the objective function [EUR-ct]
    if params['add_battery']:
        # Cost of energy throughput to the battery
        batt_operating_cost = {
            t: 0.25 * batt.block.flow_abs[t] * params['batt_op_cost']
            for t in model.timesteps
        }
        total_batt_operating_cost = sum(batt_operating_cost.values())
        objective_function -= total_batt_operating_cost
    if params['add_pv']:
        # Cost of energy produced by the PV-system
        pv_generation_cost = {
            t: 0.25 * pv.block.flow[t] * params['pv_cost']
            for t in model.timesteps
        }
        total_pv_generation_cost = sum(pv_generation_cost.values())
        objective_function -= total_pv_generation_cost
    if params['add_id_buy']:
        # Cost of energy buy at the intraday market including price switch with full load time
        if params['add_ps'] and params['full_load_time']:
            id_energy_buy_cost = {
                t: 0.25 * id_buy.block.flow[t] * (id_buy.prices[t] + ps.block.en_price[t] * 100)
                for t in model.timesteps
            }
        else:
            id_energy_buy_cost = {
                t: 0.25 * id_buy.block.flow[t] * (id_buy.prices[t] + params['net_energy_price'] * 100)
                for t in model.timesteps
            }
        total_id_energy_buy_cost = sum(id_energy_buy_cost.values())
        objective_function -= total_id_energy_buy_cost
    if params['add_id_sell']:
        # Revenue of energy sell at the intraday market
        id_energy_sell_revenue = {
            t: 0.25 * id_sell.block.flow[t] * id_sell.prices[t]
            for t in model.timesteps
        }
        total_id_energy_sell_revenue = sum(id_energy_sell_revenue.values())
        objective_function += total_id_energy_sell_revenue
    if params['add_da_buy']:
        # Cost of energy buy at the day-ahead market including price switch with full load time
        if params['add_ps'] and params['full_load_time']:
            da_energy_buy_cost = {
                t: 0.25 * da_buy.block.flow[t] * (da_buy.prices[t] + ps.block.en_price[t] * 100)
                for t in model.timesteps
            }
        else:
            da_energy_buy_cost = {
                t: 0.25 * da_buy.block.flow[t] * (da_buy.prices[t] + params['net_energy_price'] * 100)
                for t in model.timesteps
            }
        total_da_energy_buy_cost = sum(da_energy_buy_cost.values())
        objective_function -= total_da_energy_buy_cost
    if params['add_da_sell']:
        # Revenue of energy sell at the day-ahead market
        da_energy_sell_revenue = {
            t: 0.25 * da_sell.block.flow[t] * da_sell.prices[t]
            for t in model.timesteps
        }
        total_da_energy_sell_revenue = sum(da_energy_sell_revenue.values())
        objective_function += total_da_energy_sell_revenue
    if params['add_fcr']:
        fcr_capacity_revenue = {
            t: fcr.block.capacity_revenue[t] / 16
            for t in model.timesteps
        }
        total_fcr_capacity_revenue = sum(fcr_capacity_revenue.values())
        objective_function += total_fcr_capacity_revenue
    if params['add_afrrn']:
        # Revenue of energy part of aFRRn
        afrrn_energy_revenue = {
            t: 0.25 * afrrn.block.flow[t] * afrrn.energy_prices[t]
            for t in model.timesteps
        }
        total_afrrn_energy_revenue = sum(afrrn_energy_revenue.values())
        objective_function += total_afrrn_energy_revenue
        # Revenue of capacity part of aFRRn
        afrrn_capacity_revenue = {
            t: afrrn.block.capacity_revenue[t] / 16
            for t in model.timesteps
        }
        total_afrrn_capacity_revenue = sum(afrrn_capacity_revenue.values())
        objective_function += total_afrrn_capacity_revenue
    if params['add_afrrp']:
        # Revenue of energy part of aFRRp
        afrrp_energy_revenue = {
            t: 0.25 * afrrp.block.flow[t] * afrrp.energy_prices[t]
            for t in model.timesteps
        }
        total_afrrp_energy_revenue = sum(afrrp_energy_revenue.values())
        objective_function += total_afrrp_energy_revenue
        # Revenue of capacity part of aFRRp
        afrrp_capacity_revenue = {
            t: afrrp.block.capacity_revenue[t] / 16
            for t in model.timesteps
        }
        total_afrrp_capacity_revenue = sum(afrrp_capacity_revenue.values())
        objective_function += total_afrrp_capacity_revenue
    if params['add_ps']:
        if params['full_load_time']:
            net_capacity_cost = ps.block.cost[len(model.timesteps) - 1] * 100
            tflt = ps.block.total_supply_power[len(model.timesteps) - 1] / (ps.block.p_max[len(model.timesteps) - 1] + 0.01)
            tflt_percentage = tflt / len(model.timesteps) * 100
        else:
            net_capacity_cost = ps.block.p_max[len(model.timesteps) - 1] * params['net_capacity_price'] * 100
        objective_function -= net_capacity_cost

    # Set up the model
    model.objective = po.Objective(expr=objective_function, sense=po.maximize)
    solver = po.SolverFactory(params['solver'])
    # solver.options['MIPGap'] = 0.01
    # Solve the model
    meta = solver.solve(model, tee=params['see_meta'])

    # Get the results
    if params['add_battery']:
        batt_soc = [po.value(batt.block.soc[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=batt_soc,
                name='Battery SoC [kWh]',
                color='black',
                style='solid'
            )
        batt_flow = [po.value(batt.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=batt_flow,
                name='Flow to the Battery [kW]',
                color='blue',
                style='solid'
            )
    if params['add_pv']:
        pv_source_flow = [po.value(pv.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=pv_source_flow,
                name='Flow from PV-Source [kW]',
                color='orange',
                style='solid'
            )
    if params['add_id_buy']:
        id_source_flow = [po.value(id_buy.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=id_source_flow,
                name='Flow from ID-Source [kW]',
                color='red',
                style='solid'
            )
    if params['add_id_sell']:
        id_sink_flow = [po.value(id_sell.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=id_sink_flow,
                name='Flow to ID-Sink [kW]',
                color='red',
                style='dash'
            )
    if params['add_da_buy']:
        da_source_flow = [po.value(da_buy.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=da_source_flow,
                name='Flow from DA-Source [kW]',
                color='green',
                style='solid'
            )
    if params['add_da_sell']:
        da_sink_flow = [po.value(da_sell.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=da_sink_flow,
                name='Flow to DA-Sink [kW]',
                color='green',
                style='dash'
            )
    if params['add_fcr']:
        fcr_flow = [po.value(fcr.block.flow_source[t]) - po.value(fcr.block.flow_sink[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=fcr_flow,
                name='Flow from FCR-Source [kW]',
                color='magenta',
                style='solid'
            )
    if params['add_afrrn']:
        afrrn_flow = [po.value(afrrn.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=afrrn_flow,
                name='Flow from aFRRn-Source [kW]',
                color='purple',
                style='solid'
            )
            output_plot.append_curve_plot(
                data=afrrn.request_profile,
                name='aFRR- Request Profile [kW]',
                color='grey',
                style='solid'
            )
        output_dir = os.path.join(os.path.dirname(__file__), '../outputs')
        os.makedirs(output_dir, exist_ok=True)  # Ensure the directory exists
        output_path = os.path.join(output_dir, 'afrrn_clearing_prices.csv')
        pd.DataFrame({
            'Clearing Price [€/MWh]': afrrn.energy_prices[:len(model.timesteps)]*10
        }).to_csv(output_path, index=False)
    if params['add_afrrp']:
        afrrp_flow = [po.value(afrrp.block.flow[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=afrrp_flow,
                name='Flow from aFRRp-Sink [kW]',
                color='darkcyan',
                style='solid'
            )
            output_plot.append_curve_plot(
                data=afrrp.request_profile,
                name='aFRR+ Request Profile [kW]',
                color='grey',
                style='solid'
            )
        output_dir = os.path.join(os.path.dirname(__file__), '../outputs')
        os.makedirs(output_dir, exist_ok=True)  # Ensure the directory exists
        output_path = os.path.join(output_dir, 'afrrp_clearing_prices.csv')
        pd.DataFrame({
            'Clearing Price [€/MWh]': afrrp.energy_prices[:len(model.timesteps)]*10
        }).to_csv(output_path, index=False)
    if params['add_mobility']:
        charging = [po.value(batt.block.charging[t]) for t in model.timesteps]
        if params['plot_outputs']:
            output_plot.append_curve_plot(
                data=charging,
                name='Virtual Discharge [kW]',
                color='black',
                style='dash'
            )

    # Plot the outputs
    if params['plot_outputs']:
        output_plot.generate_curve_plot(show=True)

    # Print results to the console
    if params['print_results']:
        for t in range(0, len(model.timesteps)):
            print("----------------------------------------")
            print(f"Step {t}:")
            if params['add_battery']:
                batt.get_results(t=t, name="Battery")
                print(f"{'Battery Operating Cost:':<{params['val_pos']}} {po.value(batt_operating_cost[t]) / 100:.2f} €")
            if params['add_pv']:
                pv.get_results(t=t, name="PV-System")
                print(f"{f'PV Generation Cost:':<{params['val_pos']}} {po.value(pv_generation_cost[t]) / 100:.2f} €")
            if params['add_id_buy']:
                id_buy.get_results(t=t, name="ID-Source")
                print(f"{f'ID Energy Buy Cost:':<{params['val_pos']}} {po.value(id_energy_buy_cost[t]) / 100:.2f} €")
            if params['add_id_sell']:
                id_sell.get_results(t=t, name="ID-Sink")
                print(f"{f'ID Energy Sell Revenue:':<{params['val_pos']}} {po.value(id_energy_sell_revenue[t]) / 100:.2f} €")
            if params['add_da_buy']:
                da_buy.get_results(t=t, name="DA-Source")
                print(f"{f'DA Energy Buy Cost:':<{params['val_pos']}} {po.value(da_energy_buy_cost[t]) / 100:.2f} €")
            if params['add_da_sell']:
                da_sell.get_results(t=t, name="DA-Sink")
                print(f"{f'DA Energy Sell Revenue:':<{params['val_pos']}} {po.value(da_energy_sell_revenue[t]) / 100:.2f} €")
            if params['add_fcr']:
                fcr.get_results(t=t, name="FCR")
                print(f"{f'FCR Capacity Revenue:':<{params['val_pos']}} {po.value(fcr_capacity_revenue[t]) / 100:.2f} €")
            if params['add_afrrn']:
                afrrn.get_results(t=t, name="aFRRn")
                print(f"{f'aFRRn Capacity Revenue:':<{params['val_pos']}} {po.value(afrrn_capacity_revenue[t]) / 100:.2f} €")
                print(f"{f'aFRRn Energy Revenue:':<{params['val_pos']}} {po.value(afrrn_energy_revenue[t]) / 100:.2f} €")
            if params['add_afrrp']:
                afrrp.get_results(t=t, name="aFRRp")
                print(f"{f'aFRRp Capacity Revenue:':<{params['val_pos']}} {po.value(afrrp_capacity_revenue[t]) / 100:.2f} €")
                print(f"{f'aFRRp Energy Revenue:':<{params['val_pos']}} {po.value(afrrp_energy_revenue[t]) / 100:.2f} €")
            if params['add_ps']:
                ps.get_results(t=t, name='Peak Shaving')
                print(f"{f'Total Net Capacity Cost:':<{params['val_pos']}} {po.value(net_capacity_cost) / 100:.2f} €")
                if params['full_load_time']:
                    print(f"{f'Total Full Load Time Percentage:':<{params['val_pos']}} {po.value(tflt_percentage):.2f} %")
                    print(f"{f'TFLT above limit:':<{params['val_pos']}} {po.value(ps.block.delta[t].value):.1f}")

    # Print meta-data to the console
    if params['print_meta']:
        print(f"\n")
        # Amount of constraints
        amount_constraints = model.component_data_objects(po.Constraint, active=True)
        amount_constraints = len(list(amount_constraints))
        print(f"Amount of Constraints: {amount_constraints}")

        # Amount of variables
        amount_variables = model.component_data_objects(po.Var, active=True)
        amount_variables = len(list(amount_variables))
        print(f"Amount of Variables: {amount_variables}")

        # Objective function
        print(f"Objective Function Value: {po.value(model.objective) / 100:.2f} €")
        if params['add_battery']:
            print(f"- Battery Operating Cost: {-po.value(total_batt_operating_cost) / 100:.2f} €")
        if params['add_pv']:
            print(f"- PV Generation Cost: {-po.value(total_pv_generation_cost) / 100:.2f} €")
        if params['add_id_buy']:
            print(f"- ID Energy Buy Cost: {-po.value(total_id_energy_buy_cost) / 100:.2f} €")
        if params['add_id_sell']:
            print(f"- ID Energy Sell Revenue: {po.value(total_id_energy_sell_revenue) / 100:.2f} €")
        if params['add_id_buy'] and params['add_id_sell']:
            print(f"- ID Result: {(po.value(total_id_energy_sell_revenue)-po.value(total_id_energy_buy_cost)) / 100:.2f} €")
        if params['add_da_buy']:
            print(f"- DA Energy Buy Cost: {-po.value(total_da_energy_buy_cost) / 100:.2f} €")
        if params['add_da_sell']:
            print(f"- DA Energy Sell Revenue: {po.value(total_da_energy_sell_revenue) / 100:.2f} €")
        if params['add_da_buy'] and params['add_da_sell']:
            print(f"- DA Result: {(po.value(total_da_energy_sell_revenue)-po.value(total_da_energy_buy_cost)) / 100:.2f} €")
        if params['add_fcr']:
            print(f"- FCR Capacity Revenue: {po.value(total_fcr_capacity_revenue) / 100:.2f} €")
        if params['add_afrrp']:
            print(f"- aFRR+ Energy Revenue: {po.value(total_afrrp_energy_revenue) / 100:.2f} €")
            print(f"- aFRR+ Capacity Revenue: {po.value(total_afrrp_capacity_revenue) / 100:.2f} €")
            print(f"- aFRR+ Result: {(po.value(total_afrrp_energy_revenue) + po.value(total_afrrp_capacity_revenue)) / 100:.2f} €")
        if params['add_afrrn']:
            print(f"- aFRR- Energy Revenue: {po.value(total_afrrn_energy_revenue) / 100:.2f} €")
            print(f"- aFRR- Capacity Revenue: {po.value(total_afrrn_capacity_revenue) / 100:.2f} €")
            print(f"- aFRR- Result: {(po.value(total_afrrn_energy_revenue) + po.value(total_afrrn_capacity_revenue)) / 100:.2f} €")


    # Compute the program execution time
    finish_time = time.time()
    execution_time = finish_time - start_time
    print(f"\nExecution time: {execution_time:.1f} seconds.")

if __name__ == "__main__":
    main()
