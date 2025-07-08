import pandas as pd
import numpy as np
import warnings
import os

import visualizer

def get_params(path: str, scenario: str) -> dict:
    """Load parameters from a column in an Excel file"""

    # Dictionary for the parameters
    params = {}

    # Individual reader
    reader = pd.read_excel(path, engine='openpyxl')

    # Define keys for the conversion of the text in the Excel file
    conversion_map = {
        'int':      int,
        'float':    float,
        'str':      str,
        'bool':     lambda x: x.lower() == 'true',
        '':         str
    }

    # Load the values from the Excel file
    for column, row in reader.iterrows():
        name = row['Name']
        datatype = row['Datatype']
        value = row[scenario]

        # Convert the value types based on the conversion map
        try:
            value = conversion_map.get(datatype, str)(value)
            params[name] = value
        except Exception as e:
            params[name] = ''

    return params


def get_frequencies(filename: str, column_name: str) -> tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    """Get second-wise frequency data from a file in the directory and convert it to 15-min-wise"""

    # Open the directory and read the file
    path = os.path.join(os.path.dirname(__file__), filename)
    data = pd.read_csv(path, sep=",")

    # Get the second-wise frequency profile
    sec_profile = np.array(data[column_name])

    # Check for invalid value
    for idx, value in enumerate(sec_profile):
        if np.isnan(value) or np.isinf(value):
            warnings.warn(f"Invalid value of frequency data (NaN or inf) found at index {idx}: {value}")

    # Compute frequency deviations
    nominal_frequency = 50
    dead_band_lower = 0.01
    dead_band_upper = 0.2
    sec_deviations = sec_profile - nominal_frequency

    # Length of 15-min intervals in seconds
    interval_length = 15 * 60
    bid_length = 4 * 60 * 60

    # Starting indices for each 15-min window
    indices_15min = np.arange(0, len(sec_deviations), interval_length)  # [0, 900, 1800, 2700, ..., 85500]
    indices_4h = np.arange(0, len(sec_deviations), bid_length) # [0, 14400, 28800, ..., 72000]

    # Sum of positive deviations
    sec_pos_dev = sec_deviations.copy()
    sec_pos_dev[sec_pos_dev < dead_band_lower] = 0 # no deployment below 50.01 Hz
    sec_pos_dev[sec_pos_dev > dead_band_upper] = 0 # no deployment above 50.20 Hz
    # Average of deviations for every slot of 900
    min_avrg_pos_dev = np.add.reduceat(sec_pos_dev, indices_15min)/interval_length
    # Max of deviations for every slot of 14400
    pos_dev_maximum = np.array([sec_pos_dev[i:i + bid_length].max() for i in indices_4h])
    # Repeat to get size of 96 again
    pos_dev_maximum = pos_dev_maximum.repeat(16)

    # Sum of negative deviations
    sec_neg_dev = sec_deviations.copy()
    sec_neg_dev[sec_neg_dev > -dead_band_lower] = 0  # no deployment above 49.99 Hz
    sec_neg_dev[sec_neg_dev < -dead_band_upper] = 0  # no deployment below 49.80 Hz
    # Average of deviations for every slot of 900
    min_avrg_neg_dev = np.add.reduceat(sec_neg_dev, indices_15min)/interval_length
    # Max of deviations for every slot of 14400
    neg_dev_maximum = np.array([sec_neg_dev[i:i + bid_length].min() for i in indices_4h])
    # Repeat to get size of 96 again
    neg_dev_maximum = neg_dev_maximum.repeat(16)

    dev_tuple = (min_avrg_pos_dev, min_avrg_neg_dev, pos_dev_maximum, neg_dev_maximum)

    return dev_tuple

def get_prices(filename: str, column_name: str) -> np.ndarray:
    """Get price data from a file in the directory"""

    # Open the directory and read the file
    path = os.path.join(os.path.dirname(__file__), filename)
    data = pd.read_csv(path, sep=",")

    # Convert the prices from EUR/MW to ct/kW
    prices_ct_per_kw = np.array(data[column_name] / 10)

    return prices_ct_per_kw


def market_clearing(request_filename: str, bid_filename: str) -> np.ndarray:
    """Compute the marginal price in aFRR energy auction"""

    # Open the request file
    path = os.path.join(os.path.dirname(__file__), request_filename)
    data = pd.read_csv(path, sep=",")
    afrrn_request_profile = np.array(data['Data'])

    # Sum up over every 4h period
    interval_length = 16
    indices_4h = np.arange(0, len(afrrn_request_profile), interval_length)  # [0, 16, 32, ... 96]
    afrrn_request_profile_4h = np.add.reduceat(afrrn_request_profile, indices_4h)

    # Open the bid file
    path = os.path.join(os.path.dirname(__file__), bid_filename)
    bids = pd.read_csv(path, sep=",")

    # Adjust prices based on direction
    bids.loc[bids['Direction'] == 'PROVIDER_TO_GRID', 'Price [EUR/MWh]'] *= -1

    # Sort the offered capacity according to the product name
    capacity_sum = bids.groupby('Time')['Capacity [MW]'].sum()
    capacity_sum_np = capacity_sum.to_numpy()
    capacity_av_np = capacity_sum_np.copy()
    capacity_av_np = np.add.reduceat(capacity_av_np, indices_4h)/interval_length
    capacity_av_np = capacity_av_np.repeat(interval_length)

    # Sort the bids
    bids_sorted = bids.sort_values(by=['Time', 'Price [EUR/MWh]'])

    # List with all products, so POS_001 to POS_096 etc. for each day
    times = bids_sorted['Time'].unique()

    # index to match the times (str) to the request profile (int)
    t_ = 0

    # List to collect prices in order
    clearing_prices_np = np.zeros(672) # Prevent errors with mismatching length becuase of missing data points

    for t in times:
        # Filter the bids for t
        bids_t = bids_sorted[bids_sorted['Time'] == t]

        # Demand at this timestep
        demand_t = afrrn_request_profile[t_]
        # print(f'Demand: {demand_t} MW')
        print(bids_t)

        # Loop to accumulate capacity
        cumulative_capacity = 0
        clearing_price = np.nan

        for _, row in bids_t.iterrows():
            cumulative_capacity += row['Capacity [MW]']
            if cumulative_capacity >= demand_t:
                clearing_price = row['Price [EUR/MWh]']
                break

        # Convert list to numpy array and convert to ct/kWh
        clearing_prices_np[t_] = clearing_price / 10

        t_ += 1  # Move to next timestep




    ###########################################
    plot = visualizer.Visualizer('Market Clearing', 'Time', '[MW or €/MWh]', '../outputs')
    plot.append_curve_plot(afrrn_request_profile, 'aFRR Request Profile [MW]', 'black', 'solid')
    plot.append_curve_plot(capacity_sum_np, 'Offered Capacity [MW]', 'green', 'solid')
    #plot.append_curve_plot(capacity_av_np, 'Offered Capacity 4h Average [MW]', 'blue', 'solid')
    plot.append_curve_plot(clearing_prices_np*10, 'Clearing Prices [€/MWh]', 'red', 'solid')
    plot.generate_curve_plot()

    return clearing_prices_np
