from datetime import datetime
from BPTK_Py import sd_functions as sd
from BPTK_Py import Model
import pandas as pd


def datetime_to_serial(dates):
    """ Convert datetime into Excel serial number """
    # 5/24 is bodge to match excel serial conversion
    serials = []
    try:
        for date in dates:
            timestamp = datetime.timestamp(date)
            serials.append(timestamp / 86400.0 + 25569.0 - 5/24)
    except TypeError:
        date = dates
        timestamp = datetime.timestamp(date)
        serials = timestamp / 86400.0 + 25569.0 - 5/24
    return serials


def serial_to_datetime(serials):
    """ Convert Excel serial number into datetime """
    dates = []
    try:
        for serial in serials:
            seconds = (serial - 25569.0) * 86400.0
            dates.append(datetime.utcfromtimestamp(seconds))
    except TypeError:
        serial = serials
        seconds = (serial - 25569.0) * 86400.0
        dates = datetime.utcfromtimestamp(seconds)
    return dates

serial = [1000, 2000]
date = serial_to_datetime(serial)
serial2 = datetime_to_serial(date)
date2 = serial_to_datetime(serial2)

print(f"serial {serial}, date {date}, serial2 {serial2}, date2 {date2}")
print(date == date2)



def df_to_lookup(df, var_name):
    """ Create list for model lookup from central external data df """
    df = df[[var_name]].dropna().reset_index()
    df["Date"] = datetime_to_serial(df["Date"])
    list_out = df.values.tolist()
    return list_out


def create_model_stock(model, stock_name):
    """ Create stock and stock initial value """
    stock_var = model.stock(stock_name)
    stock_initial_value_var = model.constant(f"{stock_name} Initial Value")
    stock_var.initial_value = stock_initial_value_var
    return stock_var, stock_initial_value_var


def create_model_data_variable(model, df, data_name):
    """ Create a variable that reads external data from the central df """
    data_var = model.converter(data_name)
    model.points[data_name] = df_to_lookup(df, data_name)
    data_var.equation = sd.lookup(sd.time(), data_name)
    return data_var


def smooth_model_variable(model, input_var, time_constant, initial_value):
    """ Smooth a variable
    (Built-in sd.smooth function does not work properly)
    """
    smoothed_value = model.stock(f"{input_var.name} SMOOTHED")
    smoothed_value.initial_value = initial_value
    value_increase = model.flow(f"{input_var.name} SMOOTHING UP")
    value_decrease = model.flow(f"{input_var.name} SMOOTHING DOWN")
    smoothed_value.equation = value_increase - value_decrease
    value_increase.equation = (input_var - smoothed_value) / time_constant
    value_decrease.equation = (smoothed_value - input_var) / time_constant
    return smoothed_value
